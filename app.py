import os
import time

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ui import theme
from ui.api_client import ingest_document, judge_answer, run_query, save_rating

load_dotenv()

st.set_page_config(page_title="Simple RAG", page_icon="📄", layout="wide")
theme.inject_base_css()

STEP_LABELS = ["Question received", "Retrieving chunks", "Reranking", "Generating answer"]

QUALITY_KIND = {"strong_match": "success", "weak_match": "warning", "no_relevant_match": "danger"}
QUALITY_LABELS = {
    "strong_match": "Strong match",
    "weak_match": "Weak match",
    "no_relevant_match": "No relevant match",
}

theme.hero(
    "📄",
    "Simple RAG",
    "Upload a PDF, ask questions in plain English, and inspect exactly how the answer was retrieved, reranked and judged.",
)

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    if os.getenv("GROQ_API_KEY"):
        st.markdown(theme.badge("GROQ_API_KEY set", "success"), unsafe_allow_html=True)
    else:
        st.markdown(theme.badge("GROQ_API_KEY missing", "danger"), unsafe_allow_html=True)
    st.caption("Set it in your environment or a `.env` file.")
    st.divider()
    st.markdown("### 🧭 Navigate")
    st.caption("Use the **Evaluation** page for judge calibration and regression tests.")

    if st.session_state.get("ingest_info"):
        st.divider()
        st.markdown("### 📄 Current document")
        info = st.session_state.ingest_info
        st.markdown(f"**{info['filename']}**")
        st.caption(f"{info['n_chunks']} chunks · {info['duration_ms']:.0f} ms ingest")
        if st.button("🗑️ Clear conversation", width="stretch"):
            st.session_state.messages = []
            st.rerun()

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"], label_visibility="collapsed")

if "messages" not in st.session_state:
    st.session_state.messages = []

if not uploaded_file:
    st.markdown("#### 👋 Welcome")
    st.markdown("Upload a PDF above to start asking questions about its content.")
    col1, col2, col3 = st.columns(3)
    steps = [
        ("📥", "1. Upload", "Drop in a PDF — it's chunked and embedded automatically. Re-uploads are instant thanks to hash-based caching."),
        ("💬", "2. Ask", "Chat naturally about the document. Every answer is grounded in retrieved passages."),
        ("🔍", "3. Inspect", "Drill into retrieval, rerank scores, timings and an LLM judge for every response."),
    ]
    for col, (icon, title, desc) in zip((col1, col2, col3), steps):
        with col:
            st.markdown(
                f"""
                <div class="rag-card" style="min-height:170px;">
                    <div style="font-size:1.6rem;">{icon}</div>
                    <div style="font-weight:700; margin:0.35rem 0;">{title}</div>
                    <div style="color:{theme.MUTED}; font-size:0.88rem;">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.stop()

if not os.getenv("GROQ_API_KEY"):
    st.warning("GROQ_API_KEY is not set in environment. Add it to .env or environment variables to continue.")
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
cache_note = "⚡ loaded instantly from cache" if ingest_info["from_cache"] else "🧬 embedded fresh"

with st.container(border=True):
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        theme.stat("Document", ingest_info["filename"])
    with col_b:
        theme.stat("Chunks", str(ingest_info["n_chunks"]))
    with col_c:
        theme.stat("Ingest time", f"{ingest_info['duration_ms']:.0f} ms")
    st.caption(cache_note)

st.write("")


def render_assistant_message(msg: dict, idx: int) -> None:
    st.markdown(theme.steps_row(STEP_LABELS, len(STEP_LABELS)), unsafe_allow_html=True)
    st.markdown(msg["answer"])

    for issue in msg.get("issues", []):
        st.warning(f"⚠️ {issue['stage']}/{issue['type']}: {issue['detail']}")

    qs = msg["quality_signal"]
    with st.container(border=True):
        theme.section_title("📊", "Quality & performance")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            theme.stat("Top rerank", f"{qs['top_rerank_score']:.2f}" if qs["top_rerank_score"] is not None else "n/a")
        with c2:
            theme.stat("Docs used", str(qs["docs_returned"]))
        with c3:
            theme.stat("Latency", f"{msg['total_duration_ms']:.0f} ms")
        with c4:
            st.markdown(theme.badge(QUALITY_LABELS[qs["label"]], QUALITY_KIND[qs["label"]]), unsafe_allow_html=True)
            st.caption("Reranker confidence")

    tab1, tab2, tab3, tab4 = st.tabs(["🧠 Reasoning", "🔍 Retrieval", "⏱️ Timings", "📄 Sources"])
    with tab1:
        if msg.get("reasoning"):
            st.info(msg["reasoning"])
        else:
            st.caption("This model doesn't expose a separate reasoning trace.")
    with tab2:
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown("**Retrieved chunks**")
            for i, doc in enumerate(msg["steps"]["retrieve"]["documents_preview"], 1):
                st.markdown(f"**{i}.** {doc}")
        with col_r2:
            st.markdown("**Reranked results**")
            df = pd.DataFrame(msg["steps"]["rerank"]["documents"])
            st.dataframe(df, width="stretch", hide_index=True)
    with tab3:
        steps = msg["steps"]
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            theme.stat("Retrieve", f"{steps['retrieve']['duration_ms']:.0f} ms")
        with tc2:
            theme.stat("Rerank", f"{steps['rerank']['duration_ms']:.0f} ms")
        with tc3:
            theme.stat("Generate", f"{steps['generate']['duration_ms']:.0f} ms")
    with tab4:
        for i, ctx in enumerate(msg["contexts"], 1):
            st.markdown(f"**Chunk {i}:**")
            st.text(ctx)

    if st.button("🧑‍⚖️ Rate this answer", key=f"judge_btn_{idx}"):
        with st.spinner("Judging..."):
            msg["judge"] = judge_answer(msg["query"], msg["contexts"], msg["answer"], os.environ["GROQ_API_KEY"])
        st.rerun()

    if msg.get("judge"):
        judge = msg["judge"]
        with st.container(border=True):
            theme.section_title("🧑‍⚖️", "Judge evaluation")
            jc1, jc2, jc3 = st.columns(3)
            with jc1:
                theme.stat("Helpfulness", str(judge["judge"]["helpfulness"]))
            with jc2:
                theme.stat("Tone", str(judge["judge"]["tone"]))
            with jc3:
                source_ok = judge["rules"]["source_present"]
                st.markdown(
                    theme.badge("Source present" if source_ok else "No source", "success" if source_ok else "danger"),
                    unsafe_allow_html=True,
                )
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
        # Transient animated preview while waiting; render_assistant_message()
        # below renders the same steps again, permanently, as part of the message.
        progress = st.empty()
        for step_idx in range(3):
            progress.markdown(theme.steps_row(STEP_LABELS, step_idx), unsafe_allow_html=True)
            time.sleep(0.18)
        result = run_query(st.session_state.pdf_hash, query)
        progress.empty()

        msg = {"role": "assistant", "judge": None, "rating_saved": False, **result}
        st.session_state.messages.append(msg)
        render_assistant_message(msg, len(st.session_state.messages) - 1)
