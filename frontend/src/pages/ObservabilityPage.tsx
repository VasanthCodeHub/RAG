import { useCallback, useEffect, useState } from "react";
import { Activity, BarChart3, FlaskConical, Zap, RefreshCw, Trash2, PinIcon, CheckCircle2 } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ObsCache, ObsCase, ObsFailure, ObsQuery, ObsSummary } from "../api/client";
import { PageHero, Card, Button, Stat, Badge, DataTable, Tabs, TabPanel, ErrorBox, EmptyState, Notice, Collapse, Field, SkeletonStats, SkeletonCard, useToast } from "../components";
import { ms, pct, usd, num } from "../lib/format";

const TIP = { background: "var(--surface-solid)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12 };
const STAGE_COLORS = ["#22d3ee", "#a855f7", "#fbbf24", "#34d399"];

interface Data { summary: ObsSummary; queries: ObsQuery[]; failures: ObsFailure[]; cases: ObsCase[]; cache: ObsCache }

function MetricsTab({ d }: { d: Data }) {
  const s = d.summary;
  const stages = Object.entries(s.stage_avg_ms).filter(([, v]) => v != null).map(([k, v]) => ({ stage: k, ms: v as number }));
  const series = [...d.queries].sort((a, b) => String(a.ts).localeCompare(String(b.ts))).map((q, i) => ({ i: i + 1, total_ms: q.total_ms ?? 0, hit: q.cache_hit, cost: q.cost_usd ?? 0 }));
  const issues = Object.entries(s.issue_counts).map(([k, v]) => ({ k, v }));

  return (
    <div className="stack">
      <div className="grid c5 stagger">
        <Stat label="Queries" value={num(s.queries)} accent="violet" />
        <Stat label="Cache hit rate" value={pct(s.cache_hit_rate)} accent="good" hint={`${s.cache_hits} hits`} />
        <Stat label="Spend" value={usd(s.total_cost_usd, 4)} accent="warm" />
        <Stat label="Saved by cache" value={usd(s.saved_cost_usd, 4)} accent="good" />
        <Stat label="Errors / issues" value={`${s.errors} / ${s.with_issues}`} accent="warm" hint={`${s.alerts} alerts`} />
      </div>
      <div className="grid c5 stagger">
        <Stat label="p50 latency" value={ms(s.latency_ms.p50)} accent="cyan" />
        <Stat label="p95 latency" value={ms(s.latency_ms.p95)} accent="cyan" />
        <Stat label="Avg (cache hit)" value={ms(s.latency_ms.avg_cache_hit)} accent="good" />
        <Stat label="Avg (cache miss)" value={ms(s.latency_ms.avg_cache_miss)} accent="warm" />
        <Stat label="Tokens in / out" value={`${num(s.prompt_tokens)} / ${num(s.completion_tokens)}`} small accent="violet" />
      </div>

      {d.queries.length === 0 ? (
        <EmptyState icon={<BarChart3 size={28} />} title="No queries yet">Ask something on the Chat page and the metrics appear here.</EmptyState>
      ) : (
        <>
          <div className="grid c2">
            <Card title="Where the time goes" subtitle="Average ms per stage (cache misses)">
              {stages.length === 0 ? <div className="faint small">No stage data yet.</div> : (
                <div style={{ height: 240 }}>
                  <ResponsiveContainer>
                    <BarChart data={stages} layout="vertical" margin={{ left: 10 }}>
                      <CartesianGrid stroke="var(--border)" horizontal={false} />
                      <XAxis type="number" stroke="var(--text-3)" fontSize={12} />
                      <YAxis type="category" dataKey="stage" stroke="var(--text-3)" fontSize={12} width={70} />
                      <Tooltip contentStyle={TIP} cursor={{ fill: "var(--surface-2)" }} formatter={(v: number) => `${Math.round(v)} ms`} />
                      <Bar dataKey="ms" radius={[0, 8, 8, 0]} animationDuration={900}>{stages.map((_, i) => <Cell key={i} fill={STAGE_COLORS[i % 4]} />)}</Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
            <Card title="Latency per query" subtitle="Total ms, oldest to newest">
              <div style={{ height: 240 }}>
                <ResponsiveContainer>
                  <AreaChart data={series}>
                    <defs><linearGradient id="lat" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#a855f7" stopOpacity={0.6} /><stop offset="100%" stopColor="#a855f7" stopOpacity={0} /></linearGradient></defs>
                    <CartesianGrid stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="i" stroke="var(--text-3)" fontSize={12} />
                    <YAxis stroke="var(--text-3)" fontSize={12} />
                    <Tooltip contentStyle={TIP} formatter={(v: number) => `${Math.round(v)} ms`} labelFormatter={(l) => `Query #${l}`} />
                    <Area type="monotone" dataKey="total_ms" stroke="#a855f7" strokeWidth={2.5} fill="url(#lat)" animationDuration={1000} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
          {issues.length > 0 && (
            <Card title="Issue counts">
              <div className="row">{issues.map((i) => <Badge key={i.k} kind="warning">{i.k}: {i.v}</Badge>)}</div>
            </Card>
          )}
          <Card title="Recent queries">
            <DataTable
              rows={[...d.queries].reverse()}
              columns={["ts", "query_id", "query", "status", "cache_hit", "total_ms", "prompt_tokens", "completion_tokens", "cost_usd", "top_score", "issues", "alerts"]}
              render={{
                status: (v) => <Badge kind={v === "ok" ? "success" : v === "issues_found" ? "warning" : "danger"}>{String(v ?? "-")}</Badge>,
                cache_hit: (v) => (v ? <Badge kind="success">hit</Badge> : <Badge kind="neutral">miss</Badge>),
              }}
            />
          </Card>
        </>
      )}
      <div className="faint xs">Raw structured logs: logs/app.jsonl (filter on query_id). Metrics: logs/queries.jsonl.</div>
    </div>
  );
}

function FailureItem({ f, onPromoted }: { f: ObsFailure; onPromoted: () => void }) {
  const { toast } = useToast();
  const [should, setShould] = useState(true);
  const [kw, setKw] = useState("");
  const [pt, setPt] = useState(f.kinds?.[0]?.split(":").pop() ?? "");
  const [busy, setBusy] = useState(false);
  const replayable = !!f.pdf_hash && !!f.query;

  const promote = async () => {
    setBusy(true);
    try {
      const c = await api.obsPromote(f.query_id, should, kw.trim() || null, pt.trim() || null);
      toast("success", "Pinned as regression case", c.case_id);
      onPromoted();
    } catch (e) {
      toast("error", "Promote failed", e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card hover style={{ padding: 14 }}>
      <Collapse
        title={<span className="row" style={{ gap: 8 }}><code className="mono xs">{f.query_id}</code>{f.kinds?.map((k) => <Badge key={k} kind="danger">{k}</Badge>)}<span className="muted small">{f.query ?? "(no query)"}</span></span>}
      >
        <div className="stack" style={{ gap: 10 }}>
          <div className="small"><b>Answer given:</b> {f.answer || "-"}</div>
          {(f.details ?? []).map((d, i) => <div key={i} className="faint small">{d}</div>)}
          {!replayable ? (
            <Notice>No question/document recorded, so this cannot be replayed as a test.</Notice>
          ) : (
            <div className="stack" style={{ gap: 10 }}>
              <label className="check"><input type="checkbox" checked={should} onChange={(e) => setShould(e.target.checked)} /> The document contains the answer (should NOT refuse)</label>
              <div className="grid c2">
                <Field label="Correct answer must contain" hint="Case-insensitive. Leave empty to only check there is no refusal or issue."><input className="input" value={kw} onChange={(e) => setKw(e.target.value)} /></Field>
                <Field label="Problem type"><input className="input" value={pt} onChange={(e) => setPt(e.target.value)} /></Field>
              </div>
              <div><Button variant="primary" size="sm" icon={<PinIcon size={14} />} loading={busy} onClick={promote}>Promote to regression case</Button></div>
            </div>
          )}
        </div>
      </Collapse>
    </Card>
  );
}

function FailuresTab({ d, reload }: { d: Data; reload: () => void }) {
  const open = d.failures.filter((f) => f.status === "open");
  return (
    <div className="stack">
      <Card title="Failure to test loop" icon={<FlaskConical size={16} />} subtitle="Failures are captured automatically (pipeline issues, exceptions, human ratings of 2 or less). Promote one and say what a correct answer must contain; it becomes a case in eval/failure_cases.jsonl, replayed by python -m eval.failure_loop and the test suite.">
        {open.length === 0 ? (
          <div className="notice good"><CheckCircle2 size={18} /><span className="nm">No open failures.</span></div>
        ) : (
          <div className="stack stagger">{open.map((f) => <FailureItem key={f.query_id} f={f} onPromoted={reload} />)}</div>
        )}
      </Card>
      <Card title="Pinned regression cases">
        {d.cases.length === 0 ? <div className="faint small">None yet.</div> : (
          <DataTable rows={d.cases} columns={["case_id", "problem_type", "question", "should_answer", "expected_keyword", "created"]} />
        )}
      </Card>
    </div>
  );
}

function CacheTab({ d, reload }: { d: Data; reload: () => void }) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const c = d.cache;
  const clear = async () => {
    setBusy(true);
    try {
      const r = await api.obsClearCache();
      toast("success", "Cache cleared", `Removed ${r.removed} entries`);
      reload();
    } catch (e) {
      toast("error", "Could not clear cache", e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  if (c.enabled === false) return <Notice>Semantic cache is disabled (RAG_CACHE_ENABLED=0).</Notice>;
  return (
    <div className="stack">
      <div className="grid c4 stagger">
        <Stat label="Entries" value={c.entries} accent="violet" hint={c.max_entries ? `max ${c.max_entries}` : undefined} />
        <Stat label="Similarity threshold" value={c.threshold} accent="cyan" />
        <Stat label="TTL" value={`${(c.ttl_s / 3600).toFixed(0)} h`} accent="warm" />
        <Stat label="Namespaces" value={Object.keys(c.namespaces ?? {}).length} accent="good" />
      </div>
      <Card title="How it works" icon={<Zap size={16} />}>
        <p className="muted small" style={{ margin: 0 }}>A question is served from cache when it is an exact repeat, or its embedding is at least this similar to one already answered for the same document and model. Only clean, grounded answers are cached. Raise the threshold if similar-looking questions get the wrong answer.</p>
        <div style={{ margin: "14px 0" }}><Button variant="danger" icon={<Trash2 size={15} />} loading={busy} onClick={clear}>Clear cache</Button></div>
        {c.namespaces && Object.keys(c.namespaces).length > 0 && (
          <DataTable rows={Object.entries(c.namespaces).map(([k, v]) => ({ namespace: k, entries: v }))} />
        )}
      </Card>
    </div>
  );
}

export default function ObservabilityPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("metrics");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summary, queries, failures, cases, cache] = await Promise.all([
        api.obsSummary(), api.obsQueries(300), api.obsFailures(), api.obsCases(), api.obsCache(),
      ]);
      setData({ summary, queries, failures, cases, cache });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <>
      <PageHero icon={<Activity size={28} />} title="Observability, Cost and Failure Loop">
        Latency, tokens and spend per query; what the semantic cache saved; and a one-click path from a failed answer to a permanent regression test.
      </PageHero>
      <div className="row" style={{ marginBottom: 18, justifyContent: "space-between" }}>
        <Tabs active={tab} onChange={setTab} tabs={[
          { id: "metrics", label: "Metrics and cost", icon: <BarChart3 size={15} /> },
          { id: "failures", label: `Failure loop${data ? ` (${data.failures.filter((f) => f.status === "open").length})` : ""}`, icon: <FlaskConical size={15} /> },
          { id: "cache", label: "Semantic cache", icon: <Zap size={15} /> },
        ]} />
        <Button size="sm" icon={<RefreshCw size={14} />} loading={loading && !!data} onClick={load}>Refresh</Button>
      </div>
      {error && <ErrorBox error={error} onRetry={load} />}
      {!data && !error && <div className="stack"><SkeletonStats n={5} /><SkeletonStats n={5} /><SkeletonCard lines={5} /></div>}
      {data && (
        <TabPanel id={tab}>
          {tab === "metrics" && <MetricsTab d={data} />}
          {tab === "failures" && <FailuresTab d={data} reload={load} />}
          {tab === "cache" && <CacheTab d={data} reload={load} />}
        </TabPanel>
      )}
    </>
  );
}
