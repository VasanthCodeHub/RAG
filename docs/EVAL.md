# Evaluation (`eval/`)

Cheapest check first: rules (free, deterministic) → LLM judge (only for tone/helpfulness) → human rating.

| Piece | File | What it does |
|---|---|---|
| Rule checks | `judges.py::rule_check` | source present? refused when it should/shouldn't? expected keyword present? |
| LLM judge | `judges.py::LLMJudge` | scores helpfulness + tone (1–5) with a strict rubric |
| Judge calibration | `judges.py::check_judge_calibration` | judge vs hand labels; warns below 75% agreement before you trust it |
| Regression suite | `regression_cases.py`, `run_regression.py` | pinned real failures; "before" (old rerank) vs "after" per problem type |
| Failure → test loop | `failure_loop.py` | promote a logged failure into a permanent case (`failure_cases.jsonl`) |
| **End-to-end eval** | `e2e_eval.py` | whole app through its real seams (see below) |
| Hybrid-retrieval study | `insurance_eval.py` | vector vs BM25 vs hybrid on insurance claim docs |
| Agent evals | `claims_race.py`, `claims_trajectory_eval.py`, `claims_injection_eval.py` | agent vs workflow, trajectory correctness, prompt-injection before/after |
| Unit tests | `tests/` | `python -m unittest discover -s tests -t .` — 29 tests, no network |

## Run everything

```bash
python -m unittest discover -s tests -t .      # unit tests (offline, <1 s)
python run.py --no-frontend                     # terminal 1: backend
python -m eval.e2e_eval --a2a                   # terminal 2: end-to-end (needs GROQ_API_KEY)
python -m eval.run_regression                   # judge calibration + before/after regression
python -m eval.claims_trajectory_eval           # agent trajectory
python -m eval.claims_injection_eval            # agent prompt-injection
```

All are also runnable from the UI (Evaluation and Agents pages).

## End-to-end eval (`e2e_eval.py`)

Fixture: `eval/fixtures/northwind_handbook.txt` — a **non-resume** HR handbook (proves
document-agnostic behaviour) containing one planted prompt injection. 10 labelled cases:
7 facts (incl. a multi-hop comparison), 2 unanswerable (must refuse), 1 injection (must give the
real answer, not the planted one). Run through `rag` (`/query`), `agent` (`/agent/document`) and a
3-case subset through `a2a`. Pass/fail is rule-based so the score is reproducible.

Latest run (see `e2e_results.json`):

| path | pass | p50 latency | avg cost / q | avg tokens |
|---|---|---|---|---|
| rag | 100% | ≈3.0 s | $0.0002 | ≈720 |
| agent | 90–100%¹ | ≈8.2 s | $0.0002 | ≈750 |
| a2a (3 cases, both arms) | 100% | ≈12.5 s | $0.00066 | ≈2100 |

¹ the one miss was the grader, not the app — see "Failures found" in [DEMO.md](DEMO.md).

## Judge reliability

The judge is another model; it is calibrated against hand labels first (`/eval/calibration`) and
its scores sit beside the human rating in the UI. Treat judge numbers as a trend line, not truth.
