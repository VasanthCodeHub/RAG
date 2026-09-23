import os
import time

import streamlit as st
from dotenv import load_dotenv

from ui import theme
from ui.mcp_client import call_tool, list_tools

load_dotenv()

st.set_page_config(page_title="MCP", page_icon="🔌", layout="wide")
theme.inject_base_css()

QUALITY_KIND = {"strong_match": "success", "weak_match": "warning", "no_relevant_match": "danger"}
QUALITY_LABELS = {
    "strong_match": "Strong match",
    "weak_match": "Weak match",
    "no_relevant_match": "No relevant match",
}

TOOL_META = {
    "ingest_pdf": {"icon": "📥", "title": "Ingest PDF", "subtitle": "Chunk + embed a document"},
    "ask_pdf": {"icon": "💬", "title": "Ask a question", "subtitle": "Run the RAG pipeline"},
}

FIELD_META = {
    "pdf_path": {
        "icon": "📄",
        "label": "PDF file path",
        "placeholder": r"C:\Users\you\Documents\report.pdf",
        "help": "Absolute path on disk. Quotes from \"Copy as path\" are fine — they're stripped automatically.",
    },
    "groq_api_key": {
        "icon": "🔑",
        "label": "Groq API key",
        "placeholder": "leave blank to use GROQ_API_KEY from .env",
        "help": "Only needed if you want to override the server's default key for this call.",
    },
    "pdf_hash": {
        "icon": "🔗",
        "label": "Document hash",
        "placeholder": "returned by ingest_pdf",
        "help": "Auto-filled from your most recent ingest in this session.",
    },
    "question": {
        "icon": "💬",
        "label": "Your question",
        "placeholder": "What does this document say about...?",
        "help": "Ask anything grounded in the ingested document.",
    },
}

theme.hero(
    "🔌",
    "MCP Explorer",
    "A live MCP client, talking stdio JSON-RPC to mcp_server/server.py -- tools are discovered "
    "from the server at runtime, not hard-coded into this page.",
)
st.caption(
    "mcp_server/server.py proxies to the same FastAPI backend the chat page uses, so it needs to "
    "be running: `.venv/Scripts/python.exe -m uvicorn api.main:app --port 8000`"
)

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    if os.getenv("GROQ_API_KEY"):
        st.markdown(theme.badge("GROQ_API_KEY set", "success"), unsafe_allow_html=True)
    else:
        st.markdown(theme.badge("GROQ_API_KEY missing", "danger"), unsafe_allow_html=True)
    st.caption("Used by ingest_pdf if you don't pass one explicitly.")
    st.divider()
    st.markdown("### 🧭 About this page")
    st.caption(
        "Each action opens its own short-lived MCP session over stdio, the way a real MCP host "
        "would: initialize → discover tools → call a tool → close."
    )
    if st.session_state.get("mcp_last_pdf_hash"):
        st.divider()
        st.markdown("### 📄 Last ingested")
        st.code(st.session_state.mcp_last_pdf_hash, language=None)

if "mcp_tools" not in st.session_state:
    st.session_state.mcp_tools = None
if "mcp_calls" not in st.session_state:
    st.session_state.mcp_calls = []

with st.container(border=True):
    theme.section_title("1️⃣", "Discover tools")
    st.caption("Connects over stdio, sends the MCP `initialize` handshake, then lists tools the server advertises.")
    if st.button("🔍 Discover tools", type="primary"):
        with st.spinner("Connecting to mcp_server/server.py..."):
            try:
                st.session_state.mcp_tools = list_tools()
            except Exception as exc:
                st.error(f"Discovery failed: {exc}")
                st.session_state.mcp_tools = None

    discovery = st.session_state.mcp_tools
    if discovery:
        info = discovery["server_info"]
        st.markdown(
            theme.badge(f"connected · {info['name']} · MCP {info['protocol_version']}", "success"),
            unsafe_allow_html=True,
        )
        st.write("")
        cols = st.columns(len(discovery["tools"]))
        for col, tool in zip(cols, discovery["tools"]):
            meta = TOOL_META.get(tool["name"], {"icon": "🔧", "title": tool["name"], "subtitle": ""})
            with col:
                st.markdown(
                    f"""
                    <div class="rag-card" style="min-height:120px;">
                        <div style="font-size:1.6rem;">{meta['icon']}</div>
                        <div style="font-weight:700; margin:0.35rem 0;">{meta['title']}</div>
                        <div style="color:{theme.MUTED}; font-size:0.85rem;">{meta['subtitle']}</div>
                        <div style="color:{theme.MUTED}; font-size:0.75rem; margin-top:0.4rem;"><code>{tool['name']}</code></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander("Docs + JSON schema"):
                    st.markdown(tool["description"])
                    st.json(tool["input_schema"])
    else:
        st.caption("Not connected yet — click **Discover tools** above.")

st.write("")

with st.container(border=True):
    theme.section_title("2️⃣", "Call a tool")

    discovery = st.session_state.mcp_tools
    if not discovery:
        st.caption("Discover tools first to enable this.")
    else:
        tool_names = [t["name"] for t in discovery["tools"]]
        selected_name = st.radio(
            "Tool",
            tool_names,
            format_func=lambda n: f"{TOOL_META.get(n, {}).get('icon', '🔧')} {TOOL_META.get(n, {}).get('title', n)}",
            horizontal=True,
            label_visibility="collapsed",
        )
        selected_tool = next(t for t in discovery["tools"] if t["name"] == selected_name)
        schema = selected_tool["input_schema"]
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        prefill = {
            "pdf_hash": st.session_state.get("mcp_last_pdf_hash") or st.session_state.get("pdf_hash", ""),
        }

        with st.form(key=f"mcp_call_{selected_name}"):
            values = {}
            for field_name, spec in properties.items():
                meta = FIELD_META.get(
                    field_name, {"icon": "▫️", "label": spec.get("title", field_name), "placeholder": "", "help": ""}
                )
                is_required = field_name in required
                is_secret = "key" in field_name.lower() or "token" in field_name.lower()
                label = f"{meta['icon']} {meta['label']}" + (" *" if is_required else " (optional)")

                if field_name == "question":
                    entered = st.text_area(
                        label,
                        value="",
                        placeholder=meta["placeholder"],
                        help=meta["help"],
                        key=f"mcp_field_{selected_name}_{field_name}",
                        height=90,
                    )
                else:
                    entered = st.text_input(
                        label,
                        value=prefill.get(field_name, ""),
                        placeholder=meta["placeholder"],
                        type="password" if is_secret else "default",
                        help=meta["help"],
                        key=f"mcp_field_{selected_name}_{field_name}",
                    )
                if entered:
                    values[field_name] = entered

            meta = TOOL_META.get(selected_name, {"icon": "▶️", "title": selected_name})
            submitted = st.form_submit_button(f"{meta['icon']} Run {meta['title']}", type="primary")

        if submitted:
            missing = required - values.keys()
            if missing:
                st.error(f"Missing required field(s): {', '.join(sorted(missing))}")
            else:
                with st.spinner(f"Calling {selected_name}..."):
                    start = time.perf_counter()
                    try:
                        result = call_tool(selected_name, values)
                        duration_ms = (time.perf_counter() - start) * 1000
                        if selected_name == "ingest_pdf" and result.get("parsed", {}).get("pdf_hash"):
                            st.session_state.mcp_last_pdf_hash = result["parsed"]["pdf_hash"]
                        st.session_state.mcp_calls.insert(
                            0,
                            {
                                "tool": selected_name,
                                "arguments": {k: ("••••••" if "key" in k.lower() else v) for k, v in values.items()},
                                "result": result,
                                "duration_ms": duration_ms,
                            },
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Call failed: {exc}")

st.write("")


def render_ingest_result(data: dict) -> None:
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            theme.stat("Document", data["filename"])
        with c2:
            theme.stat("Chunks", str(data["n_chunks"]))
        with c3:
            theme.stat("Ingest time", f"{data['duration_ms']:.0f} ms")
        cache_note = "⚡ loaded instantly from cache" if data["from_cache"] else "🧬 embedded fresh"
        st.caption(cache_note)
        st.code(data["pdf_hash"], language=None)
        st.caption("↑ document hash — copy it into ask_pdf, or it's already auto-filled above.")


def render_ask_result(data: dict) -> None:
    st.markdown(data["answer"])
    qs = data["quality_signal"]
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            theme.stat(
                "Top rerank",
                f"{qs['top_rerank_score']:.2f}" if qs["top_rerank_score"] is not None else "n/a",
            )
        with c2:
            theme.stat("Docs used", str(qs["docs_returned"]))
        with c3:
            st.markdown(theme.badge(QUALITY_LABELS[qs["label"]], QUALITY_KIND[qs["label"]]), unsafe_allow_html=True)
            st.caption("Reranker confidence")
    with st.expander(f"📄 Source chunks ({len(data['contexts'])})"):
        for i, ctx in enumerate(data["contexts"], 1):
            st.markdown(f"**Chunk {i}:**")
            st.text(ctx)


def render_call(call: dict) -> None:
    result = call["result"]
    parsed = result.get("parsed")
    is_error = bool(result.get("is_error")) or (isinstance(parsed, dict) and "error" in parsed)

    if is_error:
        message = (parsed or {}).get("error", result.get("raw_text", "Unknown error"))
        st.error(message)
    elif call["tool"] == "ingest_pdf" and parsed:
        render_ingest_result(parsed)
    elif call["tool"] == "ask_pdf" and parsed:
        render_ask_result(parsed)
    elif parsed is not None:
        st.json(parsed)
    else:
        st.text(result.get("raw_text", ""))

    with st.expander("Raw MCP response"):
        st.json(result)


if st.session_state.mcp_calls:
    theme.section_title("📜", "Call history")
    for i, call in enumerate(st.session_state.mcp_calls):
        result = call["result"]
        parsed = result.get("parsed")
        is_error = bool(result.get("is_error")) or (isinstance(parsed, dict) and "error" in parsed)
        meta = TOOL_META.get(call["tool"], {"icon": "🔧", "title": call["tool"]})
        arg_preview = ", ".join(f"{k}={v!r}" for k, v in call["arguments"].items())
        header = f"{'❌' if is_error else '✅'} {meta['icon']} {meta['title']} · {call['duration_ms']:.0f} ms"
        with st.expander(header, expanded=(i == 0)):
            st.caption(arg_preview)
            render_call(call)
