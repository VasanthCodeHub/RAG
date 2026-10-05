import pandas as pd
import requests
import streamlit as st

from ui import api_client, theme

st.set_page_config(page_title="Observability", page_icon="📈", layout="wide")
theme.inject_base_css()

theme.hero(
    "📈",
    "Observability, Cost & Failure Loop",
    "Latency, tokens and spend per query; what the semantic cache saved; and a one-click path "
    "from a failed answer to a permanent regression test.",
)

try:
    summary = api_client.obs_summary()
    queries = api_client.obs_queries(300)
    failures = api_client.obs_failures()
except requests.RequestException as exc:
    st.error(f"Could not reach the API: {exc}")
    st.stop()


def ms(value):
    return f"{value} ms" if value is not None else "–"


tab_metrics, tab_failures, tab_cache = st.tabs(
    ["📊 Metrics & cost", "🧪 Failure → test loop", "⚡ Semantic cache"]
)

with tab_metrics:
    c = st.columns(5)
    c[0].metric("Queries", summary["queries"])
    c[1].metric("Cache hit rate", f"{summary['cache_hit_rate']:.0%}")
    c[2].metric("Spend", f"${summary['total_cost_usd']:.4f}")
    c[3].metric("Saved by cache", f"${summary['saved_cost_usd']:.4f}")
    c[4].metric("Errors / issues", f"{summary['errors']} / {summary['with_issues']}")

    lat = summary["latency_ms"]
    c = st.columns(5)
    c[0].metric("p50 latency", ms(lat["p50"]))
    c[1].metric("p95 latency", ms(lat["p95"]))
    c[2].metric("Avg (cache hit)", ms(lat["avg_cache_hit"]))
    c[3].metric("Avg (cache miss)", ms(lat["avg_cache_miss"]))
    c[4].metric("Tokens in / out", f"{summary['prompt_tokens']} / {summary['completion_tokens']}")

    if queries:
        df = pd.DataFrame(queries)
        df["ts"] = pd.to_datetime(df["ts"])
        stage_avg = pd.Series(summary["stage_avg_ms"]).dropna()
        if not stage_avg.empty:
            st.markdown("##### Where the time goes (cache misses, avg ms per stage)")
            st.bar_chart(stage_avg)
        st.markdown("##### Latency per query")
        st.line_chart(df.sort_values("ts").set_index("ts")["total_ms"])
        st.markdown("##### Recent queries")
        st.dataframe(
            df[
                [
                    "ts", "query_id", "query", "status", "cache_hit", "total_ms",
                    "prompt_tokens", "completion_tokens", "cost_usd", "top_score",
                    "issues", "alerts",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No queries yet. Ask something in the main chat; metrics appear here.")
    st.caption(
        "Raw structured logs: `logs/app.jsonl` (filter on `query_id`). Metrics: `logs/queries.jsonl`."
    )

with tab_failures:
    open_failures = [f for f in failures if f["status"] == "open"]
    st.caption(
        "Failures are captured automatically (pipeline issues, exceptions, human ratings ≤ 2). "
        "Promote one and say what a correct answer must contain; it becomes a case in "
        "`eval/failure_cases.jsonl`, replayed by `python -m eval.failure_loop` and the test suite."
    )
    if not open_failures:
        st.success("No open failures.")
    for f in open_failures:
        with st.expander(f"{f['query_id']} · {', '.join(f['kinds'])} · {f.get('query') or '(no query)'}"):
            st.markdown(f"**Answer given:** {f.get('answer') or '–'}")
            for detail in f.get("details", []):
                st.caption(detail)
            if not f.get("pdf_hash") or not f.get("query"):
                st.warning("No question/document recorded, so this can't be replayed as a test.")
                continue
            with st.form(f"promote_{f['query_id']}"):
                should_answer = st.checkbox(
                    "The document contains the answer (should NOT refuse)", value=True
                )
                keyword = st.text_input(
                    "Correct answer must contain",
                    help="Case-insensitive. Leave empty to only check there's no refusal/issue.",
                )
                problem_type = st.text_input("Problem type", value=f["kinds"][0].split(":")[-1])
                if st.form_submit_button("Promote to regression case"):
                    try:
                        case = api_client.obs_promote(f["query_id"], should_answer, keyword, problem_type)
                        st.success(f"Pinned as {case['case_id']}. It now runs with the tests.")
                    except requests.RequestException as exc:
                        st.error(str(exc))

    st.markdown("##### Pinned regression cases")
    cases = api_client.obs_cases()
    if cases:
        st.dataframe(
            pd.DataFrame(cases)[
                ["case_id", "problem_type", "question", "should_answer", "expected_keyword", "created"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("None yet.")

with tab_cache:
    stats = api_client.obs_cache()
    if stats.get("enabled") is False:
        st.warning("Semantic cache is disabled (RAG_CACHE_ENABLED=0).")
    else:
        c = st.columns(3)
        c[0].metric("Entries", stats["entries"])
        c[1].metric("Similarity threshold", stats["threshold"])
        c[2].metric("TTL", f"{stats['ttl_s'] / 3600:.0f} h")
        st.caption(
            "A question is served from cache when it is an exact repeat, or its embedding is at least "
            "this similar to one already answered for the same document + model. Only clean, grounded "
            "answers are cached. Raise the threshold if similar-looking questions get the wrong answer."
        )
        if st.button("Clear cache"):
            st.success(f"Removed {api_client.obs_clear_cache()['removed']} entries.")
