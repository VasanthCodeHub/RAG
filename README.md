# Document Q&A — RAG + Agent + MCP + A2A, in one app

Upload **any document** (PDF, DOCX, TXT, MD, HTML, CSV, JSON), ask questions, and inspect exactly how
each answer was retrieved, reranked, generated, judged, costed and logged.

```
frontend/       React + Vite UI                     docs/FRONTEND.md
backend/        FastAPI (HTTP surface)              docs/ARCHITECTURE.md
rag/            ingest · chunk · retrieve · rerank · generate · cache      docs/RAG.md
mcp_server/     MCP tools ingest_pdf / ask_pdf      docs/MCP.md
agent/          single agents (document + claims)   docs/AGENT.md
a2a/            manager + specialist agents         docs/A2A.md
eval/           judges · regression · e2e · agent evals                    docs/EVAL.md
observability/  logs · metrics · cost · failure log docs/OBSERVABILITY.md
tests/          offline unit tests
```

## Start (zero to a working answer)

```bash
pip install -r requirements.txt            # Python 3.11
cp .env.example .env                       # put GROQ_API_KEY=... in it
python run.py                              # backend :8000 + frontend :5173 (npm install on first run)
```

Open http://localhost:5173, drop in a document, ask a question. Full walkthrough with
troubleshooting: [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Verify

```bash
python -m unittest discover -s tests -t .     # 29 offline tests
python -m eval.e2e_eval --a2a                  # end-to-end (backend running, needs GROQ_API_KEY)
```

## Docs

[Architecture](docs/ARCHITECTURE.md) · [RAG](docs/RAG.md) · [Agent](docs/AGENT.md) · [MCP](docs/MCP.md) ·
[A2A](docs/A2A.md) · [Eval](docs/EVAL.md) · [Observability](docs/OBSERVABILITY.md) ·
[Frontend](docs/FRONTEND.md) · [Demo script](docs/DEMO.md) · [Weak spots & tough questions](docs/WEAK_SPOTS.md)

CLI alternative (no UI): `python cli.py path/to/file.pdf`.
