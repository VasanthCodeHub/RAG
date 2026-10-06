# Getting started (zero → first answer)

**You need:** Python 3.11, Node.js 18+, a free [Groq API key](https://console.groq.com/keys). Windows, macOS or Linux.

1. **Install Python deps** (from the repo root, ideally in a venv)
   ```bash
   python -m venv .venv
   .venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Add your key**: `cp .env.example .env`, then set `GROQ_API_KEY=...` in `.env`.
3. **Run**: `python run.py` (Windows: `./run.ps1`). First start downloads two small models
   (~100 MB, once) and runs `npm install`; allow a minute or two.
4. **Open** http://localhost:5173. The header chip should say the API is online with a key configured.
5. **Upload** a document on the Chat page, wait for the pipeline animation, then ask a question.
   You get the answer, the source chunks with relevance scores, tokens/cost, and cache status.

## What to try next
- Ask the same question twice → second answer comes from the semantic cache (~ms, $0).
- Toggle **Ask the agent** for a multi-part question ("compare X and Y").
- Rate an answer → low ratings land in Observability → Failures, where you can promote them to tests.
- MCP page: call `ask_pdf` yourself. A2A page: team vs single.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Header says API offline | backend didn't start; run `python -m uvicorn backend.main:app --port 8000` and read the error |
| "GROQ_API_KEY is not set" | add it to `.env` and restart, or paste it in the UI settings |
| 415 on upload | unsupported type; use pdf/docx/txt/md/html/csv/json |
| 422 "No extractable text" | scanned/image-only PDF (no OCR in this app) |
| `Unknown pdf_hash` | document was never ingested; upload it again |
| Port in use | stop the old process or `python run.py --port 8001` (and set `SIMPLE_RAG_API_URL`) |
