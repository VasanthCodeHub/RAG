# Simple RAG - React frontend

Vite + React 18 + TypeScript, plain CSS (design tokens + keyframes), react-router, recharts, lucide-react.

## Run

```bash
# 1. backend (from repo root)
.venv/Scripts/python.exe -m uvicorn backend.main:app --port 8000
# 2. frontend
cd frontend
npm install
npm run dev      # http://localhost:5173  (proxies /api -> http://localhost:8000, stripping /api)
npm run build    # type-check + production build into dist/
```

## Pages

| Route | What it does |
|---|---|
| `/` Chat | Drag-and-drop any PDF/DOCX/TXT/MD/HTML/CSV, animated ingest + retrieve/rerank/generate pipeline, markdown answers, sources with rerank scores, quality/usage/cost/cache chips, judge + human rating, "Ask the agent" toggle (tool-call trajectory) |
| `/evaluation` | Judge calibration, before/after regression, saved ratings + agreement |
| `/agents` | Tabs: document agent, claims agent-vs-workflow race, safety (trajectory review + prompt injection) |
| `/mcp` | Tool discovery, call forms generated from each tool's JSON schema, call history |
| `/a2a` | Agent cards, team-vs-single race, delegation trace |
| `/observability` | Metrics, charts, failure-to-test promotion, semantic cache |

The Groq key (optional; blank = server key), active document, and theme persist in localStorage and are shared by all pages.

## Structure

```
src/api/client.ts      single typed API client
src/context/           AppContext (key, document, theme, health, chat history)
src/components/        Card, Button, Badge, Stat, Tabs, Spinner/Skeleton, Toast, PipelineSteps,
                       ToolSteps, FileDropzone, Markdown, DataTable, States, Layout ...
src/components/chat|agents/   feature components
src/pages/             one file per route
src/styles/global.css  tokens, dark/light themes, animations
```
