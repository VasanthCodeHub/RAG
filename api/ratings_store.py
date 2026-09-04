"""Append-only JSONL store for human ratings of judged answers.

Mirrors the append-file pattern `rag/tracing.py: record_query_trace` already
uses for `eval/trace_report.json` -- one growing file of real records. Each
row is shaped like `eval/regression_cases.py: JUDGE_CALIBRATION_SET` entries
(question, context, answer, human_helpfulness, human_tone) plus the judge's
own scores, so it's a direct, hand-curatable feeder for expanding that
calibration set later -- promotion into it stays a deliberate manual step,
not automatic.
"""

import json
from pathlib import Path

RATINGS_FILE = Path("eval/ratings.jsonl")


def append(rating: dict) -> int:
    """Append one rating record and return the new total count."""
    RATINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RATINGS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rating, ensure_ascii=False) + "\n")
    return count()


def list_all() -> list[dict]:
    if not RATINGS_FILE.exists():
        return []
    with open(RATINGS_FILE, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def count() -> int:
    if not RATINGS_FILE.exists():
        return 0
    with open(RATINGS_FILE, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())
