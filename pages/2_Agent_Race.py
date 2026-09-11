"""Streamlit visualization of the Week 7 claims-agent-vs-workflow race (see
task.md and eval/claims_submission.md for the graded write-up). Runs the
same eval.claims_agent / eval.claims_workflow functions the CLI harness
(eval/claims_race.py) uses -- this page is a viewer/runner on top of that,
not a separate implementation.
"""

import os
import statistics
import sys

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.claims_agent import run_agent
from eval.claims_data import CLAIMS
from eval.claims_tools import ClaimsLLM
from eval.claims_workflow import run_workflow
from ui import theme

load_dotenv()

st.set_page_config(page_title="Agent Race", page_icon="🤖", layout="wide")
theme.inject_base_css()

theme.hero(
    "🤖",
    "Agent Race",
    "A budgeted claims-triage agent vs. a fixed workflow — same 3 tools, same model, "
    "same 10 claims. See exactly which tools each system called, and where the agent's "
    "iteration budget cuts it off.",
)

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    if os.getenv("GROQ_API_KEY"):
        st.markdown(theme.badge("GROQ_API_KEY set", "success"), unsafe_allow_html=True)
    else:
        st.markdown(theme.badge("GROQ_API_KEY missing", "danger"), unsafe_allow_html=True)
    st.caption("Set it in your environment or a `.env` file.")
    st.divider()
    st.caption("Full write-up: `eval/claims_submission.md`. CLI harness: `python -m eval.claims_race`.")

if not os.getenv("GROQ_API_KEY"):
    st.warning("GROQ_API_KEY is not set. Add it to .env or your environment to run the race.")
    st.stop()

if st.button("▶️ Run the race (10 claims)", type="primary"):
    llm = ClaimsLLM()
    agent_results, workflow_results = [], []
    bar = st.progress(0.0, text="Running claims...")
    for i, claim in enumerate(CLAIMS):
        agent_results.append(run_agent(claim["claim_id"], llm))
        workflow_results.append(run_workflow(claim["claim_id"], llm))
        bar.progress((i + 1) / len(CLAIMS), text=f"Ran {claim['claim_id']} ({i + 1}/{len(CLAIMS)})")
    bar.empty()
    st.session_state.race_agent_results = agent_results
    st.session_state.race_workflow_results = workflow_results

if not st.session_state.get("race_agent_results"):
    st.caption("Click **Run the race** to triage all 10 synthetic claims with both systems.")
    st.stop()

agent_results = st.session_state.race_agent_results
workflow_results = st.session_state.race_workflow_results


def summarize(results: list[dict]) -> dict:
    return {
        "pass_rate": sum(r["passed"] for r in results) / len(results),
        "p50_latency_ms": statistics.median([r["latency_ms"] for r in results]),
        "total_tokens": sum(r["total_tokens"] for r in results),
        "cost_per_claim": sum(r["cost_usd"] for r in results) / len(results),
    }


agent_summary = summarize(agent_results)
workflow_summary = summarize(workflow_results)

with st.container(border=True):
    theme.section_title("🏁", "Race result — 4 numbers per system")
    col_agent, col_workflow = st.columns(2)
    for col, label, summary in ((col_agent, "🤖 Agent", agent_summary), (col_workflow, "🧭 Workflow", workflow_summary)):
        with col:
            st.markdown(f"**{label}**")
            s1, s2 = st.columns(2)
            with s1:
                theme.stat("Pass rate", f"{summary['pass_rate']:.0%}")
                theme.stat("Total tokens", f"{summary['total_tokens']:,}")
            with s2:
                theme.stat("p50 latency", f"{summary['p50_latency_ms']:.0f} ms")
                theme.stat("Cost / claim", f"${summary['cost_per_claim']:.5f}")

st.write("")
theme.section_title("🧩", "Per-claim tool-call sequence")
st.caption("Every tool call each system actually made, in order. A red step means a budget cut the run off before it reached `compute_payout`.")

for claim, ar, wr in zip(CLAIMS, agent_results, workflow_results):
    with st.container(border=True):
        st.markdown(f"**{claim['claim_id']}** · {claim['claimant']} ({claim['claim_type']})")
        st.caption(claim["adjuster_notes"])

        col_a, col_w = st.columns(2)
        with col_a:
            st.markdown("🤖 **Agent**")
            tool_names = [entry["tool"] for entry in ar["tool_log"]]
            blocked = f"budget: {ar['budget_exceeded']}" if ar["status"] == "budget_exceeded" else None
            st.markdown(theme.tool_steps_row(tool_names, blocked), unsafe_allow_html=True)
            st.markdown(
                theme.badge("PASS" if ar["passed"] else "FAIL", "success" if ar["passed"] else "danger"),
                unsafe_allow_html=True,
            )
            st.caption(
                f"disposition={ar['disposition']}  payout={ar['payout']}  ·  "
                f"{ar['iterations_used']} iters · {ar['total_tokens']} tokens · "
                f"${ar['cost_usd']:.5f} · {ar['latency_ms']:.0f} ms"
            )
        with col_w:
            st.markdown("🧭 **Workflow**")
            tool_names = [entry["tool"] for entry in wr["tool_log"]]
            st.markdown(theme.tool_steps_row(tool_names), unsafe_allow_html=True)
            st.markdown(
                theme.badge("PASS" if wr["passed"] else "FAIL", "success" if wr["passed"] else "danger"),
                unsafe_allow_html=True,
            )
            st.caption(
                f"disposition={wr['disposition']}  payout={wr['payout']}  ·  "
                f"{wr['iterations_used']} iters · {wr['total_tokens']} tokens · "
                f"${wr['cost_usd']:.5f} · {wr['latency_ms']:.0f} ms"
            )

        st.caption(f"Ground truth: disposition={claim['expected_disposition']}  payout={claim['expected_payout']}")

st.write("")
with st.expander("Raw results table"):
    rows = []
    for claim, ar, wr in zip(CLAIMS, agent_results, workflow_results):
        for label, r in (("agent", ar), ("workflow", wr)):
            rows.append({
                "claim_id": claim["claim_id"],
                "system": label,
                "passed": r["passed"],
                "disposition": r["disposition"],
                "payout": r["payout"],
                "iterations": r["iterations_used"],
                "tokens": r["total_tokens"],
                "cost_usd": round(r["cost_usd"], 5),
                "latency_ms": round(r["latency_ms"], 1),
                "budget_exceeded": r["budget_exceeded"],
            })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
