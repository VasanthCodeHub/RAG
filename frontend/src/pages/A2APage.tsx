import { useEffect, useState } from "react";
import { Users, Play, Network, Trophy, Plug, Info } from "lucide-react";
import { api, AgentCard, A2AStats } from "../api/client";
import { PageHero, Card, Button, Stat, Badge, Field, Markdown, DataTable, Collapse, Tabs, TabPanel, ErrorBox, SkeletonCard, EmptyState, Spinner, useToast } from "../components";
import { useApp } from "../context/AppContext";
import { useAction } from "../lib/useAsync";
import { ms, qualityKind, qualityText, usd } from "../lib/format";

function StatsBlock({ title, icon, s, accent, winner }: { title: string; icon: React.ReactNode; s: A2AStats; accent: string; winner: boolean }) {
  return (
    <div className={`stack ${winner ? "winner" : ""}`} style={{ gap: 10, padding: winner ? 12 : 0, borderRadius: 16 }}>
      <div className="row" style={{ fontWeight: 700 }}>{icon}{title}{winner && <Badge kind="success"><Trophy size={12} /> winner</Badge>}</div>
      <div className="grid c3">
        <Stat label="Evidence" value={qualityText(s.quality_label)} small accent={accent} />
        <Stat label="Wall-clock" value={ms(s.latency_ms)} accent={accent} />
        <Stat label="Tokens" value={s.total_tokens != null ? s.total_tokens.toLocaleString() : "n/a"} accent={accent} />
      </div>
      <div className="faint small">{s.estimated_cost_usd != null ? `Estimated model cost: ${usd(s.estimated_cost_usd, 6)}` : "Estimated model cost: unavailable for the configured model."}</div>
    </div>
  );
}

export default function A2APage() {
  const { doc } = useApp();
  const { toast } = useToast();
  const [cards, setCards] = useState<AgentCard[] | null>(null);
  const [cardsErr, setCardsErr] = useState<string | null>(null);
  const [hash, setHash] = useState(doc?.pdf_hash ?? "");
  const [question, setQuestion] = useState("");
  const [tab, setTab] = useState("answer");
  const act = useAction((h: string, q: string) => api.a2aRace(h, q));

  useEffect(() => { api.a2aAgents().then(setCards).catch((e) => setCardsErr(e.message)); }, []);
  useEffect(() => { if (doc) setHash(doc.pdf_hash); }, [doc?.pdf_hash]);

  const run = async () => {
    if (!hash.trim() || !question.trim()) return;
    const r = await act.run(hash.trim(), question.trim());
    if (r) toast("success", "A2A race finished", `Verdict: ${r.metrics.winner}`);
  };
  const r = act.data;
  const w = r?.metrics.winner;

  return (
    <>
      <PageHero icon={<Users size={28} />} title="A2A Team vs Single Agent">
        An A2A manager delegates parallel work to two specialists. Both use the app's existing MCP ask_pdf tool; the manager races their combined evidence against one direct MCP answer.
      </PageHero>
      <div className="stack" style={{ gap: 22 }}>
        <Card title="Agent cards" icon={<Network size={16} />} subtitle="Discovered live from the running API. Each agent accepts A2A JSON-RPC message/send.">
          {!cards && !cardsErr && <SkeletonCard lines={2} />}
          {cardsErr && <ErrorBox error={`Could not discover A2A agents: ${cardsErr}`} />}
          {cards && (
            <div className="grid c3 stagger">
              {cards.map((c) => (
                <Card key={c.url} hover style={{ padding: 14 }}>
                  <div className="row" style={{ justifyContent: "space-between" }}><b>{c.name}</b>{c.version && <Badge kind="neutral">v{c.version}</Badge>}</div>
                  <div className="muted small" style={{ margin: "6px 0" }}>{c.description}</div>
                  <code className="mono xs faint" style={{ wordBreak: "break-all" }}>{c.url}</code>
                </Card>
              ))}
            </div>
          )}
        </Card>

        <Card title="Run the race" icon={<Play size={16} />}>
          <div className="stack">
            <Field label="Ingested document hash" hint={doc ? `Active document: ${doc.filename}` : "Upload a document on the Chat page - its hash is shared across pages."}>
              <input className="input mono" value={hash} onChange={(e) => setHash(e.target.value)} placeholder="pdf_hash" />
            </Field>
            <Field label="Question"><textarea className="textarea" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What does the document say about...?" /></Field>
            <div className="row">
              <Button variant="primary" icon={<Play size={15} />} loading={act.loading} disabled={!hash.trim() || !question.trim()} onClick={run}>Run the A2A race</Button>
              {act.loading && <span className="muted small row"><Spinner /> The manager is running two specialists in parallel, then the single MCP baseline...</span>}
            </div>
          </div>
        </Card>

        {act.error && <ErrorBox error={act.error} onRetry={run} />}
        {act.loading && <SkeletonCard lines={4} />}
        {!r && !act.loading && !act.error && <EmptyState icon={<Users size={28} />} title="No race yet">Enter a question above to compare the team with a single agent.</EmptyState>}

        {r && !act.loading && (
          <div className="stack enter">
            <Card glow>
              <div className="row" style={{ marginBottom: 12 }}>
                <Badge kind={w === "A2A team" ? "success" : w === "Tie" ? "warning" : "info"} dot pulse>VERDICT - {w}</Badge>
                <span className="muted small">{r.metrics.verdict_reason}</span>
              </div>
              <div className="grid c2">
                <StatsBlock title="A2A team" icon={<Users size={16} />} s={r.metrics.team} accent="violet" winner={w === "A2A team"} />
                <StatsBlock title="Single MCP agent" icon={<Plug size={16} />} s={r.metrics.single} accent="cyan" winner={w !== "A2A team" && w !== "Tie"} />
              </div>
            </Card>

            <Card title="Manager and specialist output" icon={<Users size={16} />}>
              <div className="answer"><Markdown text={r.team.answer} /></div>
              <div className="faint small" style={{ margin: "10px 0" }}>
                A2A task quality: direct specialist = <Badge kind={qualityKind(r.team.document_answer.quality_signal.label)}>{r.team.document_answer.quality_signal.label ?? "unknown"}</Badge>{" "}
                evidence reviewer = <Badge kind={qualityKind(r.team.evidence_review.quality_signal.label)}>{r.team.evidence_review.quality_signal.label ?? "unknown"}</Badge>
              </div>
              <b className="small">Delegation trace</b>
              <div style={{ margin: "8px 0 14px" }}><DataTable rows={r.team.delegations} /></div>
              <Collapse title="Specialist evidence and MCP source chunks">
                <Tabs active={tab} onChange={setTab} tabs={[{ id: "answer", label: "Document Answer" }, { id: "evidence", label: "Evidence Review" }]} />
                <TabPanel id={tab}>
                  {(() => {
                    const sp = tab === "answer" ? r.team.document_answer : r.team.evidence_review;
                    return (
                      <div className="stack" style={{ gap: 10 }}>
                        <div className="answer"><Markdown text={sp.answer} /></div>
                        {(sp.contexts ?? []).map((c, i) => <div className="source" key={i}><div className="sh"><Badge kind="info">chunk {i + 1}</Badge></div>{c}</div>)}
                      </div>
                    );
                  })()}
                </TabPanel>
              </Collapse>
            </Card>

            <Card title="Single-agent baseline" icon={<Plug size={16} />}>
              <div className="answer"><Markdown text={r.single.answer} /></div>
              <div className="faint small" style={{ margin: "10px 0" }}>
                Evidence quality: <Badge kind={qualityKind(r.single.quality_signal.label)}>{r.single.quality_signal.label ?? "unknown"}</Badge> top rerank score: {r.single.quality_signal.top_rerank_score ?? "n/a"}
              </div>
              <Collapse title={`Source chunks (${r.single.contexts?.length ?? 0})`}>
                <div className="stack" style={{ gap: 8 }}>{(r.single.contexts ?? []).map((c, i) => <div className="source" key={i}>{c}</div>)}</div>
              </Collapse>
            </Card>

            <Collapse title={<span className="row" style={{ gap: 6 }}><Info size={15} /> How this comparison is scored</span>}>
              <ul className="muted small" style={{ lineHeight: 1.7 }}>
                <li>Evidence quality is the ordinal reranker signal (no relevant match &lt; weak match &lt; strong match); the A2A score averages both specialists.</li>
                <li>Latency is measured end-to-end, with specialist calls run in parallel.</li>
                <li>Token counts come from Groq usage metadata; cost is an estimate from configured list rates and is unavailable for models without one.</li>
                <li>Verdict is lexicographic: higher evidence quality, then lower estimated cost, then lower latency. This is one measured question, not a general claim that multi-agent is better.</li>
              </ul>
            </Collapse>
          </div>
        )}
      </div>
    </>
  );
}
