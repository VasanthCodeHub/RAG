import { useState } from "react";
import { Gavel, Save, CheckCircle2 } from "lucide-react";
import { api, JudgeResult, QueryResult } from "../../api/client";
import { Button, Badge, Stat, Field, Stars, useToast, ErrorBox } from "..";
import { useApp } from "../../context/AppContext";
import { useAction } from "../../lib/useAsync";

interface Props {
  rag: QueryResult;
  judge?: JudgeResult | null;
  ratingSaved?: boolean;
  onJudge: (j: JudgeResult) => void;
  onSaved: () => void;
}

export function JudgePanel({ rag, judge, ratingSaved, onJudge, onSaved }: Props) {
  const { apiKey } = useApp();
  const { toast } = useToast();
  const [help, setHelp] = useState(3);
  const [tone, setTone] = useState(3);
  const [note, setNote] = useState("");

  const judgeAct = useAction(() => api.judge(rag.query, rag.contexts, rag.answer, apiKey || undefined));
  const saveAct = useAction(() =>
    api.saveRating({
      query_id: rag.query_id,
      question: rag.query,
      answer: rag.answer,
      contexts: rag.contexts,
      judge_helpfulness: judge?.judge.helpfulness ?? null,
      judge_tone: judge?.judge.tone ?? null,
      judge_reasoning: judge?.judge.reasoning ?? null,
      human_helpfulness: help,
      human_tone: tone,
      note: note || null,
    }),
  );

  const runJudge = async () => {
    const r = await judgeAct.run();
    if (r) onJudge(r);
    else toast("error", "Judge failed");
  };
  const save = async () => {
    const r = await saveAct.run();
    if (r) {
      toast("success", "Rating saved", "It now feeds the Evaluation page.");
      onSaved();
    }
  };

  if (!judge) {
    return (
      <div className="stack" style={{ gap: 10 }}>
        <div>
          <Button size="sm" icon={<Gavel size={15} />} loading={judgeAct.loading} onClick={runJudge}>
            Rate this answer
          </Button>
        </div>
        {judgeAct.error && <ErrorBox error={judgeAct.error} onRetry={runJudge} />}
      </div>
    );
  }

  const ok = judge.rules.source_present;
  return (
    <div className="card enter" style={{ background: "var(--surface-2)" }}>
      <div className="card-title">
        <span className="ic" style={{ background: "var(--grad-warm)" }}>
          <Gavel size={16} />
        </span>
        Judge evaluation
      </div>
      <div className="grid c3" style={{ margin: "12px 0" }}>
        <Stat label="Helpfulness" value={`${judge.judge.helpfulness} / 5`} accent="good" />
        <Stat label="Tone" value={`${judge.judge.tone} / 5`} accent="cyan" />
        <Stat label="Rule check" value={<Badge kind={ok ? "success" : "danger"}>{ok ? "Source present" : "No source"}</Badge>} accent="warm" />
      </div>
      <p className="muted small" style={{ margin: "0 0 14px" }}>
        <b>Judge reasoning:</b> {judge.judge.reasoning}
      </p>
      {ratingSaved ? (
        <div className="notice good">
          <CheckCircle2 size={18} /> <span className="nm">Your rating is saved - see it on the Evaluation page.</span>
        </div>
      ) : (
        <div className="stack" style={{ gap: 12 }}>
          <div className="small muted">Add your own rating. This feeds the judge calibration set.</div>
          <div className="grid c2">
            <Field label="Your helpfulness"><Stars value={help} onChange={setHelp} /></Field>
            <Field label="Your tone"><Stars value={tone} onChange={setTone} /></Field>
          </div>
          <Field label="Note (optional)">
            <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="What was good or bad?" />
          </Field>
          {saveAct.error && <ErrorBox error={saveAct.error} />}
          <div>
            <Button variant="primary" size="sm" icon={<Save size={15} />} loading={saveAct.loading} onClick={save}>
              Save my rating
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
