import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from eval.judges import LLMJudge, check_judge_calibration, rule_check
from eval.regression_cases import JUDGE_CALIBRATION_SET, REGRESSION_CASES, RESUME_CORPUS
from eval.run_regression import RERANK_TOP_K, combined_score, old_buggy_rerank
from rag.llm import GroqLLM
from rag.prompt import ANSWER_PROMPT
from rag.rerank import CrossEncoderRerank
from rag.retrieval import EmbeddingRetrieval

load_dotenv()

st.set_page_config(page_title="Evaluation", page_icon="🧪")
st.title("🧪 Evaluation")
st.caption(
    "Permanent regression tests built from real production failures "
    "(`eval/trace_report.json`), scored with cheap rule checks first and an "
    "LLM judge for what rules can't decide (tone, helpfulness)."
)

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

if not os.getenv("GROQ_API_KEY"):
    st.warning("Enter your Groq API key in the sidebar to run the evaluation suite.")
    st.stop()


@st.cache_resource(show_spinner="Loading models (embedding + cross-encoder)...")
def build_eval_resources(api_key: str):
    retrieval = EmbeddingRetrieval(documents=RESUME_CORPUS)
    reranker = CrossEncoderRerank(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
    llm = GroqLLM(api_key=api_key)
    return retrieval, reranker, llm


retrieval, reranker, llm = build_eval_resources(os.environ["GROQ_API_KEY"])
judge = LLMJudge(llm)

st.subheader("1. Judge calibration")
st.caption(
    "Before trusting the LLM judge on new cases, check it agrees with our "
    "own hand-labeled scores on a small, clear-cut set."
)
if st.button("Run calibration check"):
    with st.spinner("Scoring calibration set..."):
        calibration = check_judge_calibration(judge, JUDGE_CALIBRATION_SET)

    col1, col2 = st.columns(2)
    col1.metric("Helpfulness agreement", f"{calibration['helpfulness_agreement']:.0%}")
    col2.metric("Tone agreement", f"{calibration['tone_agreement']:.0%}")
    if calibration["helpfulness_agreement"] < 0.75 or calibration["tone_agreement"] < 0.75:
        st.error("Judge agreement is below 75% — treat its scores below with caution.")

    calibration_df = pd.DataFrame(
        [
            {
                "question": row["question"],
                "human_help": row["human_helpfulness"],
                "judge_help": row["judge"]["helpfulness"],
                "help_agree": row["helpfulness_agree"],
                "human_tone": row["human_tone"],
                "judge_tone": row["judge"]["tone"],
                "tone_agree": row["tone_agree"],
                "judge_reasoning": row["judge"]["reasoning"],
            }
            for row in calibration["rows"]
        ]
    )
    st.dataframe(calibration_df, width="stretch")

st.divider()
st.subheader("2. Before/after regression on real trace failures")
st.caption(
    "Each row is a real query that produced a bad answer in production. "
    '"Before" replays the old, buggy rerank fallback (collapses to 1 '
    'document); "after" uses the current pipeline.'
)

if st.button("Run regression suite", type="primary"):
    rows = []
    by_problem_type: dict[str, list[tuple[float, float]]] = {}

    progress = st.progress(0.0, text="Running cases...")
    for i, case in enumerate(REGRESSION_CASES):
        docs, _ = retrieval.retrieve(case["question"], top_k=100)

        before_docs, _ = old_buggy_rerank(reranker, case["question"], docs, RERANK_TOP_K)
        before_answer = llm.generate(
            ANSWER_PROMPT.format(query=case["question"], context="\n".join(before_docs))
        )
        after_docs, _ = reranker.rerank(case["question"], docs, top_k=RERANK_TOP_K)
        after_answer = llm.generate(
            ANSWER_PROMPT.format(query=case["question"], context="\n".join(after_docs))
        )

        scores = {}
        for label, docs_used, answer in (("before", before_docs, before_answer), ("after", after_docs, after_answer)):
            rules = rule_check(case, answer, docs_used)
            judge_result = judge.score(case["question"], "\n".join(docs_used), answer)
            score = combined_score(rules, judge_result)
            scores[label] = score
            rows.append(
                {
                    "problem_type": case["problem_type"],
                    "question": case["question"],
                    "stage": label,
                    "docs_used": len(docs_used),
                    "source_present": rules["source_present"],
                    "refusal_correct": rules["refusal_correct"],
                    "keyword_present": rules["keyword_present"],
                    "judge_helpfulness": judge_result["helpfulness"],
                    "judge_tone": judge_result["tone"],
                    "score": round(score, 2),
                    "answer": answer,
                }
            )
        by_problem_type.setdefault(case["problem_type"], []).append((scores["before"], scores["after"]))
        progress.progress((i + 1) / len(REGRESSION_CASES), text=f"Ran {i + 1}/{len(REGRESSION_CASES)} cases")

    st.markdown("#### Per-case detail")
    st.dataframe(pd.DataFrame(rows), width="stretch")

    st.markdown("#### Score per problem type (before → after)")
    summary_rows = []
    for problem_type, pairs in by_problem_type.items():
        before_avg = sum(p[0] for p in pairs) / len(pairs)
        after_avg = sum(p[1] for p in pairs) / len(pairs)
        summary_rows.append(
            {
                "problem_type": problem_type,
                "before": round(before_avg, 2),
                "after": round(after_avg, 2),
                "delta": round(after_avg - before_avg, 2),
            }
        )
    st.dataframe(pd.DataFrame(summary_rows), width="stretch")
