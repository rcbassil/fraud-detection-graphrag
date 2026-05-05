import os
import operator
from typing import Annotated, List, TypedDict, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END, START
from langchain_neo4j import Neo4jGraph
from langchain_anthropic import ChatAnthropic
# from langchain_aws import ChatBedrockConverse
# from langchain_google_genai import ChatGoogleGenerativeAI # Optional for Google ADK

load_dotenv()

# --- 1. LLM Configuration ---
# Using Claude 3.5 Sonnet via Bedrock
#llm = ChatBedrockConverse(
#    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
#    region_name="us-east-1"
#)

# This will automatically look for ANTHROPIC_API_KEY in your environment
llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    temperature=0,
    max_tokens=1024
)


# --- 2. State & Schema ---
class AgentState(TypedDict):
    query: str
    investigation_log: Annotated[List[str], operator.add]
    suspicious_players: Annotated[List[str], operator.add]
    next_step: str
    risk_score: Annotated[int, operator.add]

class SupervisorDecision(BaseModel):
    reasoning: str = Field(description="Internal logic for the next handoff.")
    next_agent: Literal["graph_agent", "vector_agent", "FINISH"]

# --- 3. The Agents (Native Functions) ---

def graph_agent(state: AgentState):
    """Queries Neo4j for players sharing identifiers (collusion patterns)."""
    graph = Neo4jGraph(url=os.getenv("NEO4J_URI"), username=os.getenv("NEO4J_USERNAME"), password=os.getenv("NEO4J_PASSWORD"), refresh_schema=False)

    res = graph.query("""
        MATCH (p1:Player)-[:LOGGED_IN_FROM|LIVES_AT]->(shared)<-[:LOGGED_IN_FROM|LIVES_AT]-(p2:Player)
        WHERE p1 <> p2
        RETURN p1.name AS player1, p2.name AS player2, labels(shared)[0] AS shared_via

        UNION

        MATCH (p1:Player)-[:PLACED_BET]->(t:Terminal)<-[:PLACED_BET]-(p2:Player)
        WHERE p1 <> p2
        RETURN p1.name AS player1, p2.name AS player2, 'Terminal' AS shared_via
    """)

    if not res:
        return {"investigation_log": ["Graph Agent: No suspicious connections found."], "suspicious_players": [], "risk_score": 0}

    flagged = set()
    details = []
    for row in res:
        flagged.add(row["player1"])
        flagged.add(row["player2"])
        details.append(f"{row['player1']} <-> {row['player2']} (shared {row['shared_via']})")

    raw_findings = "\n".join(f"  - {d}" for d in details)
    interpretation = llm.invoke(
        f"User question: {state['query']}\n\n"
        f"Graph analysis found these structural connections between players:\n{raw_findings}\n\n"
        "In 2-3 sentences, explain what these connections suggest in the context of the user's question."
    )

    log = f"Graph Agent: Found {len(details)} suspicious link(s):\n{raw_findings}\nAnalysis: {interpretation.content}"
    return {
        "investigation_log": [log],
        "suspicious_players": list(flagged),
        "risk_score": 25 * len(details),
    }

def vector_agent(state: AgentState):
    """Checks betting behavior anomalies for flagged players."""
    players = state.get("suspicious_players", [])
    if not players:
        return {"investigation_log": ["Vector Agent: No flagged players to analyze."], "risk_score": 0}

    graph = Neo4jGraph(url=os.getenv("NEO4J_URI"), username=os.getenv("NEO4J_USERNAME"), password=os.getenv("NEO4J_PASSWORD"), refresh_schema=False)
    betting_data = graph.query("""
        MATCH (p:Player)-[b:PLACED_BET]->(t:Terminal)
        WHERE p.name IN $players
        RETURN p.name AS player, p.historical_avg AS historical_avg,
               b.amount AS bet_amount, t.location AS terminal
        ORDER BY p.name
    """, params={"players": players})

    if not betting_data:
        return {"investigation_log": [f"Vector Agent: No betting records found for {', '.join(players)}."], "risk_score": 0}

    bet_summary = "\n".join(
        f"  - {row['player']}: bet ${row['bet_amount']} at {row['terminal']} (historical avg: ${row['historical_avg']})"
        for row in betting_data
    )

    analysis = llm.invoke(
        f"User question: {state['query']}\n\n"
        f"Betting behavior data for flagged players:\n{bet_summary}\n\n"
        "Analyze these betting patterns for anomalies relevant to the user's question. "
        "Flag specific deviations from historical averages. Be concise (2-3 sentences)."
    )

    log = f"Vector Agent: Betting data for {len(players)} player(s):\n{bet_summary}\nAnalysis: {analysis.content}"
    return {"investigation_log": [log], "risk_score": 15 * len(players)}

def supervisor(state: AgentState):
    """The Handoff Logic: Evaluates logs and directs the next agent."""
    structured_llm = llm.with_structured_output(SupervisorDecision)
    
    prompt = f"""
    User Query: {state['query']}
    Suspicious Players Identified: {state.get('suspicious_players', [])}
    Current Investigation Logs: {state['investigation_log']}
    Current Risk Score: {state['risk_score']}

    Agents available:
    - graph_agent: finds players sharing IPs, addresses, or terminals (structural collusion)
    - vector_agent: analyzes betting behavior anomalies for flagged players

    Decide if we need more structural data (graph_agent), behavioral data (vector_agent),
    or if we have enough to FINISH.
    """
    
    decision = structured_llm.invoke(prompt)
    print(f"--- Supervisor Reasoning: {decision.reasoning} ---")
    return {"next_step": decision.next_agent}

# --- 4. Define the Handoff Workflow ---
workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor)
workflow.add_node("graph_agent", graph_agent)
workflow.add_node("vector_agent", vector_agent)

workflow.set_entry_point("supervisor")

# The Handoff Logic
def router(state: AgentState):
    if state["next_step"] == "FINISH":
        return END
    return state["next_step"]

workflow.add_conditional_edges("supervisor", router)
workflow.add_edge("graph_agent", "supervisor")
workflow.add_edge("vector_agent", "supervisor")

app = workflow.compile()

# --- 5. Run Local Test ---
if __name__ == "__main__":

    test_query = "Analyze any suspicious activity and the players that made it"
    result = app.invoke({"query": test_query, "investigation_log": [], "suspicious_players": [], "risk_score": 0})

    print("\n--- FLAGGED PLAYERS ---")
    for player in set(result.get("suspicious_players", [])):
        print(f"  * {player}")

    print("\n--- FINAL INVESTIGATION LOG ---")
    for entry in result["investigation_log"]:
        print(f"- {entry}")

    print(f"\nFINAL RISK SCORE: {result['risk_score']}")