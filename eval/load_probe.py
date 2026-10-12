"""Concurrency probe for docs/SCALE_10X.md: fire N simultaneous real requests
at one pipeline (no cache) and report latency/throughput per stage.

    .venv/Scripts/python.exe -m eval.load_probe 1 4 8 16

Uses a temp log dir, so the real logs/ are untouched. Costs ~$0.0002/request.
"""

import json
import os
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()
os.environ["RAG_TRACE_FILE"] = ""

from eval.cost_benchmark import HANDBOOK_HASH  # noqa: E402
from eval.e2e_eval import CASES  # noqa: E402


def main(levels: list[int]) -> None:
    from eval.failure_loop import build_pipeline
    from observability import metrics

    pipe = build_pipeline(HANDBOOK_HASH)
    pipe.run("warm up", use_cache=False)
    out = []
    for n in levels:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RAG_LOG_DIR"] = tmp
            questions = [CASES[i % len(CASES)]["q"] for i in range(n)]
            started = time.perf_counter()
            errors = 0

            def one(q):
                nonlocal errors
                try:
                    pipe.run(q, use_cache=False)
                except Exception:
                    errors += 1

            with ThreadPoolExecutor(max_workers=n) as ex:
                list(ex.map(one, questions))
            wall = time.perf_counter() - started
            rows = metrics._read(metrics.queries_path())
        ok = [r for r in rows if r["status"] != "error"]
        lat = sorted(r["total_ms"] for r in ok)
        out.append(
            {
                "concurrency": n,
                "ok": len(ok),
                "errors": errors,
                "wall_s": round(wall, 1),
                "throughput_rps": round(len(ok) / wall, 2),
                "p50_ms": round(statistics.median(lat)) if lat else None,
                "p95_ms": round(lat[int(0.95 * (len(lat) - 1))]) if lat else None,
                "avg_rerank_ms": round(statistics.fmean(r["rerank_ms"] for r in ok)) if ok else None,
                "avg_generate_ms": round(statistics.fmean(r["generate_ms"] for r in ok)) if ok else None,
            }
        )
        print(json.dumps(out[-1]))


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [1, 4, 8, 16])
