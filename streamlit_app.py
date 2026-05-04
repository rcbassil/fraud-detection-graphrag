import streamlit as st
from main import app

st.set_page_config(
    page_title="Fraud Detection GraphRAG",
    page_icon="🔍",
    layout="wide",
)

st.title("Fraud Detection GraphRAG")
st.caption("Multi-agent investigation powered by Neo4j graph analysis and Claude Sonnet.")

st.divider()

query = st.text_area(
    "Investigation query",
    value="Analyze any suspicious activity and the players that made it",
    height=100,
)

run = st.button("Run Investigation", type="primary", use_container_width=True)

if run:
    risk_placeholder = st.empty()
    players_placeholder = st.empty()

    log_header = st.subheader("Live Investigation Feed")
    log_container = st.container()

    investigation_log = []
    suspicious_players = []
    risk_score = 0

    with st.spinner("Investigation in progress…"):
        for chunk in app.stream(
            {"query": query, "investigation_log": [], "suspicious_players": [], "risk_score": 0},
            stream_mode="updates",
        ):
            for node, state in chunk.items():
                # Accumulate state
                investigation_log += state.get("investigation_log", [])
                suspicious_players += state.get("suspicious_players", [])
                risk_score += state.get("risk_score", 0)

                # Show live log entry
                with log_container:
                    if state.get("investigation_log"):
                        for entry in state["investigation_log"]:
                            st.info(f"**{node}** — {entry}")
                    elif node == "supervisor" and state.get("next_step"):
                        st.write(f"_Supervisor routing to: `{state['next_step']}`_")

                # Update risk score live
                color = "normal" if risk_score < 50 else "off" if risk_score < 100 else "inverse"
                risk_placeholder.metric("Risk Score", risk_score, delta=state.get("risk_score") or None, delta_color=color)

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Flagged Players")
        unique_players = list(set(suspicious_players))
        if unique_players:
            for player in unique_players:
                st.error(f"⚠ {player}")
        else:
            st.success("No suspicious players identified.")

    with col2:
        st.subheader("Final Risk Score")
        if risk_score == 0:
            st.success(f"**{risk_score}** — No risk detected")
        elif risk_score < 50:
            st.warning(f"**{risk_score}** — Low risk")
        elif risk_score < 100:
            st.warning(f"**{risk_score}** — Medium risk")
        else:
            st.error(f"**{risk_score}** — High risk")

    st.divider()
    st.subheader("Full Investigation Log")
    for i, entry in enumerate(investigation_log):
        with st.expander(f"Entry {i + 1}", expanded=True):
            st.text(entry)
