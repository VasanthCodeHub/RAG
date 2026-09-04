import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ui.api_client import list_ratings, run_calibration, run_regression

load_dotenv()

st.set_page_config(page_title="Evaluation", page_icon="🧪", layout="wide")
st.title("🧪 Evaluation")
st.caption(
    "Permanent regression tests built from real production failures "
    "(`eval/trace_report.json`), scored with cheap rule checks first and an "
    "LLM judge for what rules can't decide (tone, helpfulness). Served by the "
    "same FastAPI backend the chat page talks to."
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

api_key = os.environ["GROQ_API_KEY"]

st.subheader("1. Judge calibration")
st.caption(
    "Before trusting the LLM judge on new cases, check it agrees with our "
    "own hand-labeled scores on a small, clear-cut set."
)
if st.button("Run calibration check"):
    with st.spinner("Scoring calibration set..."):
        calibration = run_calibration(api_key)

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
    with st.spinner("Running regression cases (retrieval + rerank + judge)..."):
        result = run_regression(api_key)

    st.markdown("#### Per-case detail")
    st.dataframe(pd.DataFrame(result["rows"]), width="stretch")

    st.markdown("#### Score per problem type (before → after)")
    st.dataframe(pd.DataFrame(result["summary"]), width="stretch")

st.divider()
st.subheader("3. Your ratings so far")
st.caption("Ratings saved from the chat page's \"Rate this answer\" flow.")
ratings = list_ratings()
if not ratings:
    st.caption("No ratings saved yet — rate an answer on the main chat page first.")
else:
    ratings_df = pd.DataFrame(ratings)
    st.dataframe(ratings_df, width="stretch")

    tolerance = 1
    help_agree = sum(
        1
        for r in ratings
        if r.get("judge_helpfulness") is not None
        and abs(r["judge_helpfulness"] - r["human_helpfulness"]) <= tolerance
    )
    tone_agree = sum(
        1
        for r in ratings
        if r.get("judge_tone") is not None and abs(r["judge_tone"] - r["human_tone"]) <= tolerance
    )
    n = len(ratings)
    col1, col2 = st.columns(2)
    col1.metric("Your vs. judge — helpfulness agreement", f"{help_agree / n:.0%}")
    col2.metric("Your vs. judge — tone agreement", f"{tone_agree / n:.0%}")
