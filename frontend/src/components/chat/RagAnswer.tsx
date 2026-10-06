import { useState } from "react";
import { Sparkles, Clock, Coins, Zap, TriangleAlert, Brain, Search, Timer, FileText } from "lucide-react";
import { QueryResult } from "../../api/client";
import { Badge, Markdown, PipelineSteps, RAG_STEPS, Tabs, TabPanel, Stat, DataTable } from "..";
import { ms, usd, qualityKind, qualityText } from "../../lib/format";

export function RagAnswer({ rag }: { rag: QueryResult }) {
  const [tab, setTab] = useState("sources");
  const s = rag.steps;
  const steps = RAG_STEPS.map((st, i) => ({
    ...st,
    duration: i === 1 ? s.retrieve.duration_ms : i === 2 ? s.rerank.duration_ms : i === 3 ? s.generate.duration_ms : null,
  }));
  const qs = rag.quality_signal;
  const scores = s.rerank.documents ?? [];
  const maxScore = Math.max(1, ...scores.map((d) => d.score));

  return (
    <div className="stack" style={{ gap: 14 }}>
      <PipelineSteps steps={steps} current={steps.length} />
      <div className="answer">
        <Markdown text={rag.answer} />
      </div>
      {rag.issues.map((iss, i) => (
        <div className="notice" key={i}>
          <TriangleAlert size={18} />
          <span className="nm">
            <b>
              {iss.stage}/{iss.type}
            </b>
            : {iss.detail}
          </span>
        </div>
      ))}
      <div className="row" style={{ gap: 8 }}>
        <Badge kind={qualityKind(qs.label)} dot>{qualityText(qs.label)}</Badge>
        <Badge kind="neutral"><Clock size={12} /> {ms(rag.total_duration_ms)}</Badge>
        <Badge kind="neutral"><Sparkles size={12} /> top rerank {qs.top_rerank_score != null ? qs.top_rerank_score.toFixed(2) : "n/a"}</Badge>
        <Badge kind="neutral"><FileText size={12} /> {qs.docs_returned} chunk{qs.docs_returned === 1 ? "" : "s"}</Badge>
        {rag.usage && (
          <>
            <Badge kind="violet">{rag.usage.total_tokens.toLocaleString()} tokens</Badge>
            <Badge kind="violet"><Coins size={12} /> {usd(rag.usage.estimated_cost_usd, 6)}</Badge>
          </>
        )}
        {rag.cache?.hit && (
          <Badge kind="success" dot>
            <Zap size={12} /> cache hit{rag.cache.similarity != null ? ` ${(rag.cache.similarity * 100).toFixed(0)}%` : ""}
            {rag.cache.saved_cost_usd != null ? ` - saved ${usd(rag.cache.saved_cost_usd, 6)}` : ""}
          </Badge>
        )}
        {rag.cache && !rag.cache.hit && <Badge kind="neutral">cache miss</Badge>}
      </div>
      {rag.cache?.hit && rag.cache.matched_query && (
        <div className="faint small">Matched earlier question: "{rag.cache.matched_query}"{rag.cache.age_s != null ? ` (${Math.round(rag.cache.age_s)}s ago)` : ""}</div>
      )}

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "sources", label: `Sources (${rag.contexts.length})`, icon: <FileText size={14} /> },
          { id: "reasoning", label: "Reasoning", icon: <Brain size={14} /> },
          { id: "retrieval", label: "Retrieval", icon: <Search size={14} /> },
          { id: "timings", label: "Timings", icon: <Timer size={14} /> },
        ]}
      />
      <TabPanel id={tab}>
        {tab === "sources" && (
          <div className="stack" style={{ gap: 10 }}>
            {rag.contexts.length === 0 && <div className="faint small">No source chunks were used.</div>}
            {rag.contexts.map((c, i) => {
              const sc = scores[i]?.score;
              return (
                <div className="source" key={i}>
                  <div className="sh">
                    <Badge kind="info">#{i + 1}</Badge>
                    {sc != null && (
                      <>
                        <span className="scorebar"><i style={{ width: `${Math.max(4, Math.min(100, (sc / maxScore) * 100))}%` }} /></span>
                        <span className="mono xs muted">{sc.toFixed(3)}</span>
                      </>
                    )}
                  </div>
                  {c}
                </div>
              );
            })}
          </div>
        )}
        {tab === "reasoning" &&
          (rag.reasoning ? <div className="source" style={{ fontStyle: "italic" }}>{rag.reasoning}</div> : <div className="faint small">This model did not expose a separate reasoning trace.</div>)}
        {tab === "retrieval" && (
          <div className="grid c2">
            <div className="stack" style={{ gap: 8 }}>
              <b className="small">Retrieved chunks ({s.retrieve.docs_retrieved ?? "?"} of top-{s.retrieve.top_k ?? "?"})</b>
              {(s.retrieve.documents_preview ?? []).map((d, i) => (
                <div className="source" key={i}>{d}</div>
              ))}
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <b className="small">Reranked results</b>
              <DataTable rows={scores.map((d, i) => ({ rank: i + 1, score: d.score, text: d.text }))} />
            </div>
          </div>
        )}
        {tab === "timings" && (
          <div className="grid c4">
            <Stat label="Retrieve" value={ms(s.retrieve.duration_ms)} accent="cyan" />
            <Stat label="Rerank" value={ms(s.rerank.duration_ms)} accent="violet" />
            <Stat label="Generate" value={ms(s.generate.duration_ms)} accent="warm" />
            <Stat label="Total" value={ms(rag.total_duration_ms)} accent="good" />
          </div>
        )}
      </TabPanel>
    </div>
  );
}
