import { useState } from "react";
import { Bot, Play } from "lucide-react";
import { api } from "../../api/client";
import { useApp } from "../../context/AppContext";
import { useAction } from "../../lib/useAsync";
import { Card, Button, Field, NoDocument, ErrorBox, EmptyState, useToast } from "..";
import { AgentAnswer } from "../chat/AgentAnswer";
import { PendingAnswer } from "../chat/PendingAnswer";

export function DocumentAgentTab() {
  const { doc } = useApp();
  const { toast } = useToast();
  const [q, setQ] = useState("");
  const act = useAction((hash: string, question: string) => api.documentAgent(hash, question));

  if (!doc) return <NoDocument />;
  const run = async () => {
    if (!q.trim()) return;
    const r = await act.run(doc.pdf_hash, q.trim());
    if (r) toast("success", "Agent finished", `${r.iterations_used} iterations`);
  };

  return (
    <div className="stack">
      <Card
        title="Single tool-calling document agent"
        icon={<Bot size={16} />}
        subtitle={`One agent, one tool (search_document over ${doc.filename}). It decides what to search, may search again, then answers - within an iteration budget.`}
      >
        <Field label="Question">
          <textarea className="textarea" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask something that may need more than one search..." />
        </Field>
        <div style={{ marginTop: 12 }}>
          <Button variant="primary" icon={<Play size={15} />} loading={act.loading} disabled={!q.trim()} onClick={run}>Run agent</Button>
        </div>
      </Card>
      {act.loading && <Card><PendingAnswer mode="agent" /></Card>}
      {act.error && <ErrorBox error={act.error} onRetry={run} />}
      {act.data && !act.loading && <Card glow><AgentAnswer agent={act.data} /></Card>}
      {!act.data && !act.loading && !act.error && <EmptyState icon={<Bot size={28} />} title="No run yet">Ask a question to watch the agent choose and call its tools.</EmptyState>}
    </div>
  );
}
