import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ui.api_client import ingest_document, judge_answer, run_query, save_rating

load_dotenv()

st.set_page_config(page_title="Simple RAG", page_icon="📄", layout="wide")
st.markdown(
    """
    <style>
    h1 { color: #1a73e8; }
    div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    div[data-testid="stChatMessage"] { border-radius: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

QUALITY_COLORS = {"strong_match": "green", "weak_match": "orange", "no_relevant_match": "red"}
QUALITY_LABELS = {
    "strong_match": "Strong match",
    "weak_match": "Weak match",
    "no_relevant_match": "No relevant match",
}

st.title("📄 Simple RAG — ask questions about a PDF")

with st.sidebar:
    st.subheader("Settings")
    api_key_input = st.text_input(
        "Groq API key",
        value=os.getenv("GROQ_API_KEY", ""),
        type="password",
        help="Get one at https://console.groq.com/keys",
    )
    if api_key_input:
        os.environ["GROQ_API_KEY"] = api_key_input
    st.caption("This UI talks to a separate FastAPI backend — see the Evaluation page for judge/regression tools.")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if "messages" not in st.session_state:
    st.session_state.messages = []

if not uploaded_file:
    st.info("Upload a PDF to get started.")
    st.stop()

if not os.getenv("GROQ_API_KEY"):
    st.warning("Enter your Groq API key in the sidebar to continue.")
    st.stop()

file_id = f"{uploaded_file.name}-{uploaded_file.size}"
if st.session_state.get("uploaded_file_id") != file_id:
    with st.spinner("Ingesting document..."):
        ingest_info = ingest_document(uploaded_file.getvalue(), uploaded_file.name, os.environ["GROQ_API_KEY"])
    st.session_state.uploaded_file_id = file_id
    st.session_state.ingest_info = ingest_info
    st.session_state.pdf_hash = ingest_info["pdf_hash"]
    st.session_state.messages = []

ingest_info = st.session_state.ingest_info
cache_note = "⚡ loaded instantly from cache" if ingest_info["from_cache"] else "embedded fresh"
st.caption(
    f"Loaded **{ingest_info['filename']}** into **{ingest_info['n_chunks']}** chunks "
    f"({cache_note} in {ingest_info['duration_ms']:.0f} ms)."
)


def render_assistant_message(msg: dict, idx: int) -> None:
    st.markdown(msg["answer"])

    qs = msg["quality_signal"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Top rerank score",
        f"{qs['top_rerank_score']:.2f}" if qs["top_rerank_score"] is not None else "n/a",
    )
    c2.metric("Docs used", qs["docs_returned"])
    c3.metric("Latency", f"{msg['total_duration_ms']:.0f} ms")
    with c4:
        st.badge(QUALITY_LABELS[qs["label"]], color=QUALITY_COLORS[qs["label"]])
        st.caption("Reranker confidence, not a verified hit-rate.")

    for issue in msg.get("issues", []):
        st.warning(f"⚠️ {issue['stage']}/{issue['type']}: {issue['detail']}")

    tab_reasoning, tab_retrieved, tab_reranked, tab_timings, tab_sources = st.tabs(
        ["🧠 Reasoning", "🔍 Retrieved", "🎯 Reranked", "⏱️ Timings", "📄 Sources"]
    )
    with tab_reasoning:
        if msg.get("reasoning"):
            st.info(msg["reasoning"])
        else:
            st.caption("This model doesn't expose a separate reasoning trace.")
    with tab_retrieved:
        for i, doc in enumerate(msg["steps"]["retrieve"]["documents_preview"], 1):
            st.markdown(f"**{i}.** {doc}")
    with tab_reranked:
        st.dataframe(pd.DataFrame(msg["steps"]["rerank"]["documents"]), width="stretch", hide_index=True)
    with tab_timings:
        steps = msg["steps"]
        tc1, tc2, tc3 = st.columns(3)
        tc1.metric("Retrieve", f"{steps['retrieve']['duration_ms']:.0f} ms")
        tc2.metric("Rerank", f"{steps['rerank']['duration_ms']:.0f} ms")
        tc3.metric("Generate", f"{steps['generate']['duration_ms']:.0f} ms")
    with tab_sources:
        for i, ctx in enumerate(msg["contexts"], 1):
            st.markdown(f"**Chunk {i}:**")
            st.text(ctx)

    if st.button("🧑‍⚖️ Rate this answer", key=f"judge_btn_{idx}"):
        with st.spinner("Judging..."):
            msg["judge"] = judge_answer(msg["query"], msg["contexts"], msg["answer"], os.environ["GROQ_API_KEY"])
        st.rerun()

    if msg.get("judge"):
        judge = msg["judge"]
        jc1, jc2, jc3 = st.columns(3)
        jc1.metric("Judge: helpfulness", judge["judge"]["helpfulness"])
        jc2.metric("Judge: tone", judge["judge"]["tone"])
        with jc3:
            source_ok = judge["rules"]["source_present"]
            st.badge("Source present" if source_ok else "No source", color="green" if source_ok else "red")
        st.caption(f"Judge's reasoning: {judge['judge']['reasoning']}")

        if not msg.get("rating_saved"):
            with st.form(key=f"rating_form_{idx}"):
                st.write("Add your own rating — this feeds the judge calibration set:")
                rc1, rc2 = st.columns(2)
                human_help = rc1.slider("Your helpfulness score", 1, 5, 3, key=f"hh_{idx}")
                human_tone = rc2.slider("Your tone score", 1, 5, 3, key=f"ht_{idx}")
                note = st.text_input("Note (optional)", key=f"note_{idx}")
                if st.form_submit_button("Save my rating"):
                    save_rating(
                        {
                            "query_id": msg["query_id"],
                            "question": msg["query"],
                            "answer": msg["answer"],
                            "contexts": msg["contexts"],
                            "judge_helpfulness": judge["judge"]["helpfulness"],
                            "judge_tone": judge["judge"]["tone"],
                            "judge_reasoning": judge["judge"]["reasoning"],
                            "human_helpfulness": human_help,
                            "human_tone": human_tone,
                            "note": note or None,
                        }
                    )
                    msg["rating_saved"] = True
                    st.rerun()
        else:
            st.caption("✅ Your rating has been saved — see it on the Evaluation page.")


for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            render_assistant_message(msg, i)

query = st.chat_input("Ask a question about the document...")
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = run_query(st.session_state.pdf_hash, query)
        msg = {"role": "assistant", "judge": None, "rating_saved": False, **result}
        st.session_state.messages.append(msg)
        render_assistant_message(msg, len(st.session_state.messages) - 1)
