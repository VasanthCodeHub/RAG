import { Clock, Coins, Repeat, TriangleAlert } from "lucide-react";
import { DocumentAgentResult } from "../../api/client";
import { Badge, Markdown, ToolSteps, Collapse } from "..";
import { ms, usd, qualityKind, qualityText } from "../../lib/format";

export function AgentAnswer({ agent }: { agent: DocumentAgentResult }) {
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="card" style={{ background: "var(--surface-2)", padding: 14 }}>
        <div className="small muted" style={{ marginBottom: 8, fontWeight: 600 }}>Agent trajectory</div>
        <ToolSteps tools={agent.tool_log} blocked={agent.budget_exceeded ? `budget: ${agent.budget_exceeded}` : null} />
      </div>
      <div className="answer">
        <Markdown text={agent.answer || "(the agent returned no answer)"} />
      </div>
      {agent.status !== "ok" && (
        <div className="notice">
          <TriangleAlert size={18} />
          <span className="nm">Agent status: <b>{agent.status}</b>{agent.budget_exceeded ? ` (budget exceeded: ${agent.budget_exceeded})` : ""}</span>
        </div>
      )}
      <div className="row" style={{ gap: 8 }}>
        <Badge kind="neutral"><Repeat size={12} /> {agent.iterations_used} iteration{agent.iterations_used === 1 ? "" : "s"}</Badge>
        <Badge kind="neutral"><Clock size={12} /> {ms(agent.latency_ms)}</Badge>
        <Badge kind="violet">{agent.total_tokens.toLocaleString()} tokens</Badge>
        <Badge kind="violet"><Coins size={12} /> {usd(agent.cost_usd, 6)}</Badge>
      </div>
      <Collapse title={`Tool calls (${agent.tool_log.length})`} open={agent.tool_log.length > 0}>
        <div className="stack" style={{ gap: 10 }}>
          {agent.tool_log.map((t, i) => (
            <div className="source" key={i}>
              <div className="sh">
                <Badge kind="violet">iter {t.iteration}</Badge>
                <span className="mono">{t.tool}</span>
                {t.quality && <Badge kind={qualityKind(t.quality)}>{qualityText(t.quality)}</Badge>}
                {t.latency_ms != null && <span className="xs faint">{ms(t.latency_ms)}</span>}
              </div>
              {t.question && <div><b>Query:</b> {t.question}</div>}
              {t.answer && <div style={{ marginTop: 4 }}><b>Result:</b> {t.answer}</div>}
              {t.error && <div style={{ marginTop: 4, color: "var(--rose)" }}>Error: {t.error}</div>}
            </div>
          ))}
        </div>
      </Collapse>
    </div>
  );
}
