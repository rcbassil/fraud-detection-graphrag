# Fraud Detection GraphRAG

A multi-agent fraud detection system that combines graph-based structural analysis (Neo4j) with behavioral anomaly detection, orchestrated by an LLM supervisor using LangGraph.

## How it works

The system runs three agents in a loop coordinated by a supervisor:

1. **Supervisor** — an LLM (Claude Sonnet 4.6) that reads the investigation log and decides which agent to call next, or when to finish.
2. **Graph Agent** — queries Neo4j for players sharing IP addresses, home addresses, or betting terminals — structural patterns indicative of collusion.
3. **Vector Agent** — analyzes betting behavior anomalies (frequency spikes, coordinated timing) for the players flagged by the graph agent.

Each agent appends to a shared `investigation_log` and accumulates a `risk_score`. The supervisor routes between agents until it has enough evidence to `FINISH`.

```
START → supervisor → graph_agent → supervisor → vector_agent → supervisor → END
```

## Graph schema

```
(Player)-[:LOGGED_IN_FROM]->(IPAddress)
(Player)-[:LIVES_AT]->(Address)
(Player)-[:PLACED_BET]->(Terminal)
```

## Web Interface

A Streamlit UI is included for interactive investigations:

```bash
uv run streamlit run streamlit_app.py
```

Open http://localhost:8501, enter your query, and click **Run Investigation**. The interface streams supervisor decisions and agent findings live, then summarises flagged players and the final risk score.

## Docs

![Architecture diagram](docs/architecture1.svg)

![Architecture diagram](docs/architecture2.svg)

## Setup

**Prerequisites:** Python 3.12+, a running Neo4j instance, an Anthropic API key.

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Create a `.env` file:
   ```
   ANTHROPIC_API_KEY=...
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=...
   ```

3. Seed the database with test data:
   ```bash
   uv run populate_neo4j.py
   ```

4. Run the investigation:
   ```bash
   uv run main.py
   ```

## Example output

```
--- Supervisor Reasoning: Starting with structural analysis to find shared identifiers. ---
--- Supervisor Reasoning: Behavioral analysis needed for flagged players. ---
--- Supervisor Reasoning: Sufficient evidence gathered. Finalizing. ---

--- FLAGGED PLAYERS ---
  * John Doe
  * Jane Smith

--- FINAL INVESTIGATION LOG ---
- Graph Agent: Found 3 suspicious link(s):
    - John Doe <-> Jane Smith (shared IPAddress)
    - John Doe <-> Jane Smith (shared Address)
    - John Doe <-> Jane Smith (shared Terminal)
- Vector Agent: Analyzed 2 flagged player(s): John Doe, Jane Smith. Behavioral baseline shows a 300% increase in betting frequency and coordinated bet timing.

FINAL RISK SCORE: 105
```
