import { useEffect, useState } from "react";
import { Plug, Search, Play, Wrench, CircleCheck, CircleX, History, FileDown, MessageCircleQuestion } from "lucide-react";
import { api, McpCallResult, McpTool, McpTools } from "../api/client";
import { PageHero, Card, Button, Badge, Stat, Field, Collapse, Json, ErrorBox, Markdown, SkeletonCard, EmptyState, useToast, NoDocument } from "../components";
import { useApp } from "../context/AppContext";
import { ms, qualityKind, qualityText } from "../lib/format";

interface CallRecord { id: number; tool: string; args: Record<string, unknown>; result: McpCallResult; duration: number }

const TOOL_ICONS: Record<string, React.ReactNode> = {
  ingest_pdf: <FileDown size={18} />,
  ask_pdf: <MessageCircleQuestion size={18} />,
};

function fieldType(spec: any): string {
  if (spec.type) return spec.type;
  const t = (spec.anyOf ?? []).map((a: any) => a.type).find((x: string) => x && x !== "null");
  return t ?? "string";
}

function ResultView({ call }: { call: CallRecord }) {
  const p = call.result.parsed;
  const isErr = call.result.is_error || (p && typeof p === "object" && "error" in p);
  if (isErr) return <ErrorBox error={String((p && p.error) || call.result.raw_text || "Unknown error")} />;
  return (
    <div className="stack" style={{ gap: 12 }}>
      {p && typeof p === "object" && "pdf_hash" in p && "n_chunks" in p && (
        <div className="grid c3">
          <Stat label="Document" value={p.filename} small accent="violet" />
          <Stat label="Chunks" value={p.n_chunks} accent="cyan" />
          <Stat label="Source" value={p.from_cache ? "Cache" : "Fresh embed"} small accent="good" hint={p.duration_ms != null ? ms(p.duration_ms) : undefined} />
          <div style={{ gridColumn: "1 / -1" }} className="small muted">Hash: <code className="mono">{p.pdf_hash}</code></div>
        </div>
      )}
      {p && typeof p === "object" && "answer" in p && (
        <>
          <div className="answer"><Markdown text={String(p.answer)} /></div>
          {p.quality_signal && (
            <div className="row">
              <Badge kind={qualityKind(p.quality_signal.label)} dot>{qualityText(String(p.quality_signal.label))}</Badge>
              {p.quality_signal.top_rerank_score != null && <Badge kind="neutral">top rerank {Number(p.quality_signal.top_rerank_score).toFixed(2)}</Badge>}
            </div>
          )}
          {Array.isArray(p.contexts) && p.contexts.length > 0 && (
            <Collapse title={`Source chunks (${p.contexts.length})`}>
              <div className="stack" style={{ gap: 8 }}>{p.contexts.map((c: string, i: number) => <div className="source" key={i}>{c}</div>)}</div>
            </Collapse>
          )}
        </>
      )}
      {(!p || typeof p !== "object" || !("answer" in p || "pdf_hash" in p)) && <Json data={p ?? call.result.raw_text} />}
      <Collapse title="Raw MCP response"><Json data={call.result} /></Collapse>
    </div>
  );
}

function CallForm({ tool, onCall }: { tool: McpTool; onCall: (args: Record<string, unknown>) => Promise<void> }) {
  const { doc } = useApp();
  const props = tool.input_schema.properties ?? {};
  const required = new Set(tool.input_schema.required ?? []);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const init: Record<string, string> = {};
    if ("pdf_hash" in props && doc) init.pdf_hash = doc.pdf_hash;
    setValues(init);
    setErr(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool.name, doc?.pdf_hash]);

  const submit = async () => {
    const args: Record<string, unknown> = {};
    for (const [k, spec] of Object.entries(props)) {
      const v = values[k]?.trim();
      if (!v) continue;
      const t = fieldType(spec);
      args[k] = t === "integer" ? parseInt(v, 10) : t === "number" ? parseFloat(v) : t === "boolean" ? v === "true" : v.replace(/^"(.*)"$/, "$1");
    }
    const missing = [...required].filter((k) => !(k in args));
    if (missing.length) return setErr(`Missing required field(s): ${missing.join(", ")}`);
    setErr(null);
    setBusy(true);
    await onCall(args);
    setBusy(false);
  };

  return (
    <div className="stack">
      {Object.entries(props).map(([k, spec]) => {
        const t = fieldType(spec);
        const secret = /key|token|secret/i.test(k);
        const label = (spec.title ?? k) + (required.has(k) ? " *" : " (optional)");
        const hint = spec.description ?? (k === "pdf_path" ? "Absolute path on the machine running the API server. Quotes from Copy as path are stripped." : k === "pdf_hash" ? "Auto-filled from the active document." : undefined);
        return (
          <Field key={k} label={<><code className="mono">{k}</code> {label}</>} hint={hint}>
            {k === "question" ? (
              <textarea className="textarea" value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })} placeholder="What does the document say about...?" />
            ) : t === "boolean" ? (
              <select className="select" value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })}>
                <option value="">(unset)</option><option value="true">true</option><option value="false">false</option>
              </select>
            ) : spec.enum ? (
              <select className="select" value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })}>
                <option value="">(unset)</option>{spec.enum.map((o) => <option key={String(o)} value={String(o)}>{String(o)}</option>)}
              </select>
            ) : (
              <input
                className="input"
                type={secret ? "password" : t === "integer" || t === "number" ? "number" : "text"}
                value={values[k] ?? ""}
                placeholder={secret ? "leave blank to use the server key" : k === "pdf_path" ? "C:\\Users\\you\\Documents\\report.pdf" : ""}
                onChange={(e) => setValues({ ...values, [k]: e.target.value })}
                autoComplete="off"
              />
            )}
          </Field>
        );
      })}
      {Object.keys(props).length === 0 && <div className="faint small">This tool takes no arguments.</div>}
      {err && <ErrorBox error={err} />}
      <div><Button variant="primary" icon={<Play size={15} />} loading={busy} onClick={submit}>Run {tool.name}</Button></div>
    </div>
  );
}

export default function McpPage() {
  const { toast } = useToast();
  const { doc } = useApp();
  const [tools, setTools] = useState<McpTools | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [calls, setCalls] = useState<CallRecord[]>([]);

  const discover = async (notify = true) => {
    setLoading(true);
    setError(null);
    try {
      const t = await api.mcpTools();
      setTools(t);
      setSelected((s) => s ?? t.tools[0]?.name ?? null);
      if (notify) toast("success", "MCP connected", `${t.tools.length} tools from ${t.server_info.name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { discover(false); /* eslint-disable-next-line */ }, []);

  const tool = tools?.tools.find((t) => t.name === selected);

  const doCall = async (args: Record<string, unknown>) => {
    if (!tool) return;
    const start = performance.now();
    try {
      const result = await api.mcpCall(tool.name, args);
      const safeArgs = Object.fromEntries(Object.entries(args).map(([k, v]) => [k, /key/i.test(k) ? "******" : v]));
      setCalls((c) => [{ id: Date.now(), tool: tool.name, args: safeArgs, result, duration: performance.now() - start }, ...c]);
      toast(result.is_error ? "error" : "success", result.is_error ? "Tool returned an error" : `${tool.name} OK`);
    } catch (e) {
      toast("error", "Call failed", e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <>
      <PageHero icon={<Plug size={28} />} title="MCP Explorer">
        A live MCP client talking stdio JSON-RPC to mcp_server/server.py. Tools are discovered from the server at runtime, and each call form below is generated from the tool's JSON schema.
      </PageHero>
      <div className="stack" style={{ gap: 22 }}>
        <Card
          title="1. Discover tools"
          icon={<Search size={16} />}
          subtitle="Connects, sends the MCP initialize handshake, then lists the tools the server advertises."
          action={<Button variant="primary" icon={<Search size={15} />} loading={loading} onClick={() => discover()}>{tools ? "Rediscover" : "Discover tools"}</Button>}
        >
          {loading && !tools && <SkeletonCard lines={2} />}
          {error && <ErrorBox error={error} onRetry={() => discover()} />}
          {tools && (
            <div className="stack">
              <div><Badge kind="success" dot pulse>connected - {tools.server_info.name} - MCP {tools.server_info.protocol_version}</Badge></div>
              <div className="grid c3 stagger">
                {tools.tools.map((t) => (
                  <Card key={t.name} hover glow={t.name === selected} style={{ cursor: "pointer" }}>
                    <div onClick={() => setSelected(t.name)}>
                      <div style={{ width: 40, height: 40, borderRadius: 12, display: "grid", placeItems: "center", color: "#fff", background: "var(--grad-cool)", marginBottom: 10 }}>{TOOL_ICONS[t.name] ?? <Wrench size={18} />}</div>
                      <b className="mono">{t.name}</b>
                      <div className="muted small" style={{ margin: "6px 0", display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{t.description.trim().split("\n")[0]}</div>
                      <div className="row" style={{ gap: 6 }}>{Object.keys(t.input_schema.properties ?? {}).map((p) => <span className="ftype" key={p}>{p}</span>)}</div>
                    </div>
                    <div onClick={(e) => e.stopPropagation()} style={{ marginTop: 8 }}>
                      <Collapse title="Docs + JSON schema"><div className="stack" style={{ gap: 8 }}><pre className="json">{t.description.trim()}</pre><Json data={t.input_schema} /></div></Collapse>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card title="2. Call a tool" icon={<Play size={16} />} subtitle={tool ? <>Selected: <b className="mono">{tool.name}</b></> : undefined}>
          {!tools ? (
            <div className="faint small">Discover tools first to enable this.</div>
          ) : tool ? (
            <>
              {tool.name === "ask_pdf" && !doc && <div style={{ marginBottom: 12 }}><NoDocument /></div>}
              <CallForm tool={tool} onCall={doCall} />
            </>
          ) : <EmptyState title="Select a tool above" />}
        </Card>

        <Card title="Call history" icon={<History size={16} />}>
          {calls.length === 0 ? (
            <EmptyState icon={<History size={28} />} title="No calls yet">Run a tool above and its result appears here.</EmptyState>
          ) : (
            <div className="stack">
              {calls.map((c, i) => {
                const err = c.result.is_error || (c.result.parsed && typeof c.result.parsed === "object" && "error" in c.result.parsed);
                return (
                  <details key={c.id} className="collapse card" open={i === 0} style={{ padding: 14 }}>
                    <summary>
                      {err ? <CircleX size={16} style={{ color: "var(--rose)" }} /> : <CircleCheck size={16} style={{ color: "var(--emerald)" }} />}
                      <span className="mono">{c.tool}</span><span className="faint xs">{ms(c.duration)}</span>
                      <span className="faint xs" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 380 }}>{Object.entries(c.args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")}</span>
                    </summary>
                    <div className="cbody"><ResultView call={c} /></div>
                  </details>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
