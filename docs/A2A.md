# A2A — Agent-to-Agent (`a2a/`)

Implements the [A2A protocol](https://a2a-protocol.org) subset needed for a manager that delegates
to specialist agents: Agent Cards + JSON-RPC `message/send`.

## Agents

| Agent | Job |
|---|---|
| `manager` — Document Research Manager | Delegates to both specialists in parallel, runs a direct MCP baseline, compares |
| `document-answer` | Answers the question directly from the document (MCP `ask_pdf`) |
| `evidence-reviewer` | Independently looks for supporting passages, conditions, exceptions, uncertainty (MCP `ask_pdf`) |

## Files

- `a2a/protocol.py` — agent registry, `agent_card()`, `task_response()`, `message_text()` validation
- `a2a/manager.py` — orchestration: `_run_manager`, `_send_to_agent`, `_ask_mcp`, `_usage`, `_metrics`
- `backend/routers/a2a.py` — HTTP/JSON-RPC surface only

## Endpoints

- `GET /.well-known/agent-card.json` — the manager's card
- `GET /a2a/agents`, `GET /a2a/{agent}/.well-known/agent-card.json`
- `POST /a2a/{agent}` — JSON-RPC 2.0 `message/send`; the message is one text part containing
  `{"pdf_hash": "...", "question": "..."}`; reply is a completed `task` with a text artifact.
  Errors use JSON-RPC codes (`-32601` unknown method/agent, `-32602` bad params, `-32000` agent failure).
  Input limits: message ≤ 6000 chars, question ≤ 2000.

## The comparison ("race")

Team = two specialists in parallel; Single = one MCP `ask_pdf`. Winner rule, in order:
1. higher mean **retrieved-evidence quality** (`strong_match`=2, `weak`=1, `none`=0),
2. else lower **estimated cost**, 3. else lower **latency**, else tie.

Measured on the e2e set: the team costs ≈3× the tokens (≈$0.00066 vs ≈$0.0002) and ≈4× the latency
(≈12 s vs ≈3 s) and, because both specialists query the same retriever, mostly ties on evidence
quality — so a single call usually wins. A2A earns its keep when specialists have *different*
tools/knowledge (separate services, teams or vendors), not as a way to ask the same index twice.

## Tests

`tests/test_a2a.py` — card shape, message validation, task wrapping, metric/winner logic,
and the manager's parallel fan-out with mocked agents.
