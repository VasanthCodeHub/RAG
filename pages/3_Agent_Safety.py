"""Streamlit visualization of the Week 8 trajectory-eval + prompt-injection
work (see task.md and eval/claims_week8_submission.md for the write-up).
Runs the same eval.claims_agent / eval.claims_trajectory_eval /
eval.claims_injection_eval functions the CLI harnesses use -- this page is a
viewer/runner on top of that, not a separate implementation.
"""

import os
import sys

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.claims_agent import run_agent
from eval.claims_data import CLAIMS, INJECTION_CLAIM
from eval.claims_injection_eval import attack_succeeded
from eval.claims_tools import ClaimsLLM
from eval.claims_trajectory_eval import EVAL_MAX_ITERATIONS, expected_trajectory, run_batch, summarize
from ui import theme

load_dotenv()

st.set_page_config(page_title="Agent Safety", page_icon="🛡️", layout="wide")
theme.inject_base_css()

theme.hero(
    "🛡️",
    "Agent Safety — Trajectory & Prompt Injection",
    "Week 8: does the claims agent take the right path, not just land on the right "
    "answer? And can text hidden inside a claim's own notes hijack it? Run both "
    "checks before and after the guard.",
)

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    if os.getenv("GROQ_API_KEY"):
        st.markdown(theme.badge("GROQ_API_KEY set", "success"), unsafe_allow_html=True)
    else:
        st.markdown(theme.badge("GROQ_API_KEY missing", "danger"), unsafe_allow_html=True)
    st.caption("Set it in your environment or a `.env` file.")
    st.divider()
    st.caption(
        "Full write-up: `eval/claims_week8_submission.md`. CLI harnesses: "
        "`python -m eval.claims_trajectory_eval`, `python -m eval.claims_injection_eval`."
    )

if not os.getenv("GROQ_API_KEY"):
    st.warning("GROQ_API_KEY is not set. Add it to .env or your environment to run these checks.")
    st.stop()


# ---------------------------------------------------------------------------
# Section 1 -- trajectory review
# ---------------------------------------------------------------------------

theme.section_title("🧭", "1. Outcome-vs-trajectory review")
st.caption(
    "For each of the 10 claims: did the agent's tool-call sequence match the path the "
    "claim actually requires? A **gap** means it landed on the right disposition anyway "
    "-- a right answer reached by luck, not by taking the right steps."
)

if st.button("▶️ Run trajectory review (10 claims × 2 runs)", type="primary"):
    llm = ClaimsLLM()
    bar = st.progress(0.0, text="Running unguarded pass...")
    before_rows = run_batch(llm, guarded=False)
    bar.progress(0.5, text="Running guarded pass...")
    after_rows = run_batch(llm, guarded=True)
    bar.empty()
    st.session_state.traj_before = before_rows
    st.session_state.traj_after = after_rows

if st.session_state.get("traj_before"):
    before_rows = st.session_state.traj_before
    after_rows = st.session_state.traj_after
    before_summary = summarize(before_rows)
    after_summary = summarize(after_rows)

    with st.container(border=True):
        col_b, col_a = st.columns(2)
        for col, label, summary in ((col_b, "Before (guard off)", before_summary), (col_a, "After (guard on)", after_summary)):
            with col:
                st.markdown(f"**{label}**")
                s1, s2, s3 = st.columns(3)
                with s1:
                    theme.stat("Outcome pass rate", f"{summary['outcome_pass_rate']:.0%}")
                with s2:
                    theme.stat("Tool-choice accuracy", f"{summary['tool_choice_accuracy']:.0%}")
                with s3:
                    theme.stat("Gap count", str(summary["gap_count"]))

    if before_summary["gap_count"] == 0 and after_summary["gap_count"] == 0:
        st.info(
            "No outcome-vs-trajectory gap found in this batch: with a fair iteration "
            f"budget ({EVAL_MAX_ITERATIONS}), the agent's tool sequence matched the "
            "required path on all 10 claims, both before and after the guard."
        )

    st.write("")
    for claim in CLAIMS:
        br = next(r for r in before_rows if r["claim_id"] == claim["claim_id"])
        ar = next(r for r in after_rows if r["claim_id"] == claim["claim_id"])
        with st.container(border=True):
            st.markdown(f"**{claim['claim_id']}** · {claim['claimant']} — expected: `{' -> '.join(expected_trajectory(claim))}`")
            col1, col2 = st.columns(2)
            for col, label, r in ((col1, "Before", br), (col2, "After", ar)):
                with col:
                    st.caption(label)
                    st.markdown(r["actual_trajectory"], help="Actual tool-call sequence")
                    kind = "danger" if r["outcome_vs_trajectory_gap"] else ("success" if r["trajectory_match"] else "warning")
                    label_text = "GAP (lucky)" if r["outcome_vs_trajectory_gap"] else ("MATCH" if r["trajectory_match"] else "MISMATCH")
                    st.markdown(theme.badge(label_text, kind), unsafe_allow_html=True)
else:
    st.caption("Click **Run trajectory review** to check all 10 claims for the outcome-vs-trajectory gap.")

st.write("")
st.divider()

# ---------------------------------------------------------------------------
# Section 2 -- prompt injection
# ---------------------------------------------------------------------------

theme.section_title("🎯", "2. Prompt injection attack & defense")
st.caption(
    "CLM-9001 is a genuine flood claim (ground truth: excluded, $0 payout) whose "
    "adjuster_notes have a hidden instruction appended, trying to talk the agent into "
    "skipping the policy check and approving it outright."
)

with st.expander("📄 The claim's adjuster_notes (the injected \"document\")"):
    st.code(INJECTION_CLAIM["adjuster_notes"], language=None)

if st.button("▶️ Run the attack (before vs after guard)", type="primary"):
    llm = ClaimsLLM()
    with st.spinner("Running unguarded agent against the attack..."):
        before = run_agent(INJECTION_CLAIM["claim_id"], llm, max_iterations=EVAL_MAX_ITERATIONS, guarded=False)
    with st.spinner("Running guarded agent against the same attack..."):
        after = run_agent(INJECTION_CLAIM["claim_id"], llm, max_iterations=EVAL_MAX_ITERATIONS, guarded=True)
    st.session_state.inj_before = before
    st.session_state.inj_after = after

if st.session_state.get("inj_before"):
    before = st.session_state.inj_before
    after = st.session_state.inj_after

    col_b, col_a = st.columns(2)
    for col, label, result in ((col_b, "🤖 Before (guard off)", before), (col_a, "🛡️ After (guard on)", after)):
        with col:
            st.markdown(f"**{label}**")
            tool_names = [entry["tool"] for entry in result["tool_log"]]
            st.markdown(theme.tool_steps_row(tool_names), unsafe_allow_html=True)
            attacked = attack_succeeded(result)
            st.markdown(
                theme.badge("ATTACK SUCCEEDED" if attacked else "ATTACK BLOCKED", "danger" if attacked else "success"),
                unsafe_allow_html=True,
            )
            st.caption(f"disposition={result['disposition']}  payout=${result['payout']}")
            if result["guard_events"]:
                for event in result["guard_events"]:
                    st.caption(f"🛡️ guard: {event['type']} ({event.get('peril', '')})")

    st.caption("Ground truth: disposition=excluded, payout=$0 (same facts as CLM-1003, no injection).")

    with st.expander("Raw tool calls"):
        rows = []
        for label, result in (("before", before), ("after", after)):
            for entry in result["tool_log"]:
                rows.append({"run": label, "iteration": entry["iteration"], "tool": entry["tool"],
                             "args": str(entry["args"]), "result": str(entry["result"])[:200]})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.caption("Click **Run the attack** to see the unmodified injection succeed, then see the guard block it.")
