import os

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from ui import theme
from ui.a2a_client import BASE_URL, run_race

load_dotenv()

st.set_page_config(page_title="A2A Team", page_icon="🧑‍🤝‍🧑", layout="wide")
theme.inject_base_css()

theme.hero(
    "🧑‍🤝‍🧑",
    "A2A Team vs. Single Agent",
    "An A2A manager delegates parallel work to two specialists. Both use this app's existing "
    "MCP ask_pdf tool; the manager races their combined evidence against one direct MCP answer.",
)

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    st.caption(f"FastAPI: `{BASE_URL}`")
    if os.getenv("GROQ_API_KEY"):
        st.markdown(theme.badge("GROQ_API_KEY set", "success"), unsafe_allow_html=True)
    else:
        st.markdown(theme.badge("GROQ_API_KEY missing", "warning"), unsafe_allow_html=True)
    st.caption("The backend/MCP server must have a Groq key configured.")
    st.divider()
    st.markdown("### 🧭 Agent roles")
    st.caption("Manager → Document Answer + Evidence Review → existing MCP ask_pdf.")

try:
    cards_response = requests.get(f"{BASE_URL}/a2a/agents", timeout=5)
    cards_response.raise_for_status()
    cards = cards_response.json()
except requests.RequestException as exc:
    st.error(f"Could not discover A2A agents from the API: {exc}")
    st.stop()

with st.expander("A2A agent cards and protocol"):
    st.caption("Discovered from the running API. The manager and specialists accept A2A JSON-RPC `message/send` requests.")
    for card in cards:
        st.markdown(f"**{card['name']}** · `{card['url']}`")
        st.caption(card["description"])

default_hash = (
    st.session_state.get("mcp_last_pdf_hash")
    or st.session_state.get("pdf_hash")
    or ""
)
with st.form("a2a_race"):
    pdf_hash = st.text_input(
        "Ingested document hash",
        value=default_hash,
        help="Ingest a PDF in the main chat or MCP Explorer first; its hash is shared across pages.",
    )
    question = st.text_area(
        "Question",
        placeholder="What does the document say about...?",
        height=100,
    )
    submitted = st.form_submit_button("▶️ Run the A2A race", type="primary")

if submitted:
    if not pdf_hash.strip() or not question.strip():
        st.error("Enter an ingested document hash and a question.")
    else:
        try:
            with st.spinner(
                "The manager is running two specialist tasks in parallel, then the single MCP baseline..."
            ):
                st.session_state.a2a_race_result = run_race(pdf_hash.strip(), question.strip())
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            st.error(f"The A2A race failed: {exc}")

result = st.session_state.get("a2a_race_result")
if not result:
    st.info("Ingest a document using the chat or MCP Explorer, then ask a question above to compare the two approaches.")
    st.stop()

team = result["team"]
solo = result["single"]
metrics = result["metrics"]

winner = metrics["winner"]
kind = "success" if winner == "A2A team" else "warning" if winner == "Tie" else "info"
st.markdown(
    theme.badge(f"VERDICT · {winner}", kind),
    unsafe_allow_html=True,
)
st.caption(metrics["verdict_reason"])

with st.container(border=True):
    col_team, col_solo = st.columns(2)
    for col, label, stats in (
        (col_team, "🧑‍🤝‍🧑 A2A team", metrics["team"]),
        (col_solo, "🔌 Single MCP agent", metrics["single"]),
    ):
        with col:
            st.markdown(f"**{label}**")
            m1, m2, m3 = st.columns(3)
            with m1:
                theme.stat("Evidence quality", stats["quality_label"].replace("_", " ").title())
            with m2:
                theme.stat("Wall-clock", f"{stats['latency_ms']:.0f} ms")
            with m3:
                token_text = f"{stats['total_tokens']:,}" if stats["total_tokens"] is not None else "n/a"
                theme.stat("Model tokens", token_text)
            cost = stats["estimated_cost_usd"]
            st.caption(
                f"Estimated model cost: ${cost:.6f}"
                if cost is not None
                else "Estimated model cost: unavailable for the configured model."
            )

st.write("")
theme.section_title("🧑‍🤝‍🧑", "Manager and specialist output")
with st.container(border=True):
    st.markdown(team["answer"])
    direct_signal = team["document_answer"]["quality_signal"]
    evidence_signal = team["evidence_review"]["quality_signal"]
    st.caption(
        "A2A task quality: "
        f"direct specialist = {direct_signal.get('label', 'unknown')}; "
        f"evidence reviewer = {evidence_signal.get('label', 'unknown')}"
    )

delegations = team["delegations"]
st.markdown("**Delegation trace**")
st.dataframe(pd.DataFrame(delegations), width="stretch", hide_index=True)

with st.expander("Specialist evidence and MCP source chunks"):
    answer_tab, evidence_tab = st.tabs(["Document Answer", "Evidence Review"])
    for tab, specialist in (
        (answer_tab, team["document_answer"]),
        (evidence_tab, team["evidence_review"]),
    ):
        with tab:
            st.markdown(specialist["answer"])
            for index, context in enumerate(specialist.get("contexts", []), start=1):
                st.markdown(f"**Source chunk {index}**")
                st.text(context)

st.write("")
theme.section_title("🔌", "Single-agent baseline")
with st.container(border=True):
    st.markdown(solo["answer"])
    signal = solo["quality_signal"]
    st.caption(
        f"Evidence quality: {signal.get('label', 'unknown')} · "
        f"top rerank score: {signal.get('top_rerank_score', 'n/a')}"
    )
    with st.expander(f"Source chunks ({len(solo.get('contexts', []))})"):
        for index, context in enumerate(solo.get("contexts", []), start=1):
            st.markdown(f"**Source chunk {index}**")
            st.text(context)

with st.expander("How this comparison is scored"):
    st.markdown(
        "- Evidence quality is the ordinal reranker signal (no relevant match < weak match < strong match); "
        "the A2A score averages both specialists.\n"
        "- Latency is measured end-to-end, with specialist calls run in parallel.\n"
        "- Token counts come from Groq usage metadata. Model cost is an estimate using the configured "
        "`openai/gpt-oss-120b` list rates ($0.15/M prompt, $0.75/M completion tokens); it is unavailable "
        "for other models without a configured rate.\n"
        "- Verdict is lexicographic: higher evidence quality, then lower estimated cost, then lower latency. "
        "This is one measured question, not a general claim that multi-agent is better."
    )
