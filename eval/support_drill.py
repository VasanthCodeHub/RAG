"""Support drill: from a vague complaint to the one request that caused it.

"It gave a wrong answer yesterday" arrives with no query_id. This tool uses
only what a customer can tell you -- roughly when, a few words of the
question, maybe which session -- to narrow the log to a short list, then
opens one request and prints everything needed to explain it.

    # 1. narrow: a few words + a time window (UTC dates or ISO timestamps)
    python -m eval.support_drill find --keyword "medical certificate" \
        --since 2026-10-06 --until 2026-10-07

    # 2. open one: the full row, its log lines, its failure record
    python -m eval.support_drill trace 831f3491

`find` also takes --session, --status (ok|issues_found|error), --min-cost and
--slow-ms. Suspects are listed worst-first so the likely culprit is on top.
Read order and the worked example: docs/SUPPORT_DRILL.md.
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from observability import metrics


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def suspicion(row: dict) -> list[str]:
    """Why a row looks bad. More reasons = higher in the list."""
    reasons = []
    if row.get("status") == "error":
        reasons.append("error")
    if row.get("issues"):
        reasons.extend(row["issues"])
    if row.get("alerts"):
        reasons.extend(row["alerts"])
    if row.get("top_score") is not None and row["top_score"] <= 0 and not row.get("issues"):
        reasons.append("low_score")
    return reasons


def find(
    keyword: str | None = None,
    since: str | None = None,
    until: str | None = None,
    session: str | None = None,
    status: str | None = None,
    min_cost: float | None = None,
    slow_ms: float | None = None,
    rows: list[dict] | None = None,
) -> list[dict]:
    """Filter the per-request log. Every filter is optional and they combine."""
    rows = metrics._read(metrics.queries_path()) if rows is None else rows
    lo, hi = _parse_ts(since), _parse_ts(until)
    words = [w.lower() for w in (keyword or "").split()]
    out = []
    for row in rows:
        ts = _parse_ts(row.get("ts"))
        if lo and ts and ts < lo:
            continue
        if hi and ts and ts >= hi:
            continue
        haystack = f"{row.get('query') or ''} {row.get('answer') or ''}".lower()
        if words and not all(w in haystack for w in words):
            continue
        if session and row.get("session_id") != session:
            continue
        if status and row.get("status") != status:
            continue
        if min_cost is not None and (row.get("cost_usd") or 0) < min_cost:
            continue
        if slow_ms is not None and (row.get("total_ms") or 0) < slow_ms:
            continue
        out.append(row)
    out.sort(key=lambda r: (-len(suspicion(r)), r.get("ts") or ""))
    return out


def log_lines(query_id: str) -> list[dict]:
    """Every structured log line stamped with this query_id (also the rotated
    app.jsonl.N backups, so an older request is still findable)."""
    base = metrics.log_dir() / "app.jsonl"
    paths = sorted(base.parent.glob("app.jsonl*"), key=lambda p: p.stat().st_mtime)
    lines = []
    for path in paths:
        for row in metrics._read(path):
            if row.get("query_id") == query_id:
                lines.append(row)
    return sorted(lines, key=lambda r: r.get("ts", ""))


def trace(query_id: str) -> dict:
    """Everything known about one request, from the three logs."""
    row = metrics.find_query(query_id)
    if row is None:
        raise KeyError(query_id)
    return {
        "request": row,
        "log_lines": log_lines(query_id),
        "failure": metrics.get_failure(query_id),
        "suspicion": suspicion(row),
    }


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------


def _short(text, n):
    text = (text or "").replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


def print_find(rows: list[dict], limit: int = 15) -> None:
    print(f"{len(rows)} request(s) match\n")
    print(f"{'query_id':<10}{'time (UTC)':<17}{'status':<13}{'ms':>7} {'$':>9}  {'why suspect':<22}question")
    for r in rows[:limit]:
        print(
            f"{r.get('query_id', '?'):<10}{(r.get('ts') or '')[:16]:<17}{r.get('status', '?'):<13}"
            f"{(r.get('total_ms') or 0):>7.0f} {(r.get('cost_usd') or 0):>9.5f}  "
            f"{_short(','.join(suspicion(r)) or '-', 21):<22}{_short(r.get('query'), 50)}"
        )
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more (narrow with --keyword/--since/--until)")


def print_trace(t: dict) -> None:
    r = t["request"]
    print(f"REQUEST  query_id={r['query_id']}  request_id={r.get('request_id')}  session={r.get('session_id')}")
    print(f"WHEN     {r.get('ts')}   document={r.get('pdf_hash')}")
    print(f"MODEL    {r.get('model') or 'not logged'}   prompt={r.get('prompt_version') or 'not logged'}")
    print(f"STATUS   {r.get('status')}  issues={r.get('issues')}  alerts={r.get('alerts')}  error={r.get('error')}")
    print(f"\nQUESTION {r.get('query')}")
    answer = r.get("answer") or (t["failure"] or {}).get("answer")
    print(f"ANSWER   {answer or 'not logged (row pre-dates answer logging)'}")
    print("\nCHUNKS SENT TO THE MODEL")
    for c in r.get("chunks") or []:
        print(f"  [{c.get('chunk_id')}] score={c.get('score')}  {_short(c.get('preview'), 90)}")
    if not r.get("chunks"):
        print("  not logged (row pre-dates chunk logging); top rerank score:", r.get("top_score"))
    print("\nTIME AND COST BY STEP")
    for step in ("cache_lookup_ms", "retrieve_ms", "rerank_ms", "generate_ms"):
        print(f"  {step[:-3]:<13}{r.get(step) if r.get(step) is not None else '-':>8} ms")
    print(f"  {'total':<13}{r.get('total_ms'):>8} ms   tokens in/out={r.get('prompt_tokens')}/{r.get('completion_tokens')}"
          f"   cost=${(r.get('cost_usd') or 0):.5f}   cache_hit={r.get('cache_hit')}")
    print(f"\nLOG LINES ({len(t['log_lines'])})")
    for line in t["log_lines"]:
        print(f"  {line['ts'][11:23]} {line['level']:<7}{_short(line['msg'], 110)}")
    if t["failure"]:
        f = t["failure"]
        print(f"\nFAILURE RECORD  kinds={f['kinds']}  status={f['status']}  case_id={f.get('case_id')}")


def main(argv=None) -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="narrow the log from a vague complaint")
    f.add_argument("--keyword")
    f.add_argument("--since")
    f.add_argument("--until")
    f.add_argument("--session")
    f.add_argument("--status")
    f.add_argument("--min-cost", type=float)
    f.add_argument("--slow-ms", type=float)
    f.add_argument("--limit", type=int, default=15)
    t = sub.add_parser("trace", help="everything about one request")
    t.add_argument("query_id")
    t.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "find":
        print_find(
            find(args.keyword, args.since, args.until, args.session, args.status, args.min_cost, args.slow_ms),
            args.limit,
        )
        return 0
    try:
        result = trace(args.query_id)
    except KeyError:
        print(f"No request with query_id={args.query_id} in {metrics.queries_path()}")
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print_trace(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
