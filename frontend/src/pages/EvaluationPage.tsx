import { useEffect, useState } from "react";
import { FlaskConical, Scale, GitCompareArrows, Star, Play, RefreshCw } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, CalibrationResult, RegressionResult, Rating } from "../api/client";
import { PageHero, Card, Button, Stat, Badge, DataTable, ErrorBox, EmptyState, Notice, SkeletonCard, useToast, Spinner } from "../components";
import { useApp } from "../context/AppContext";
import { useAction } from "../lib/useAsync";
import { pct } from "../lib/format";

const CHART_TIP = { background: "var(--surface-solid)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12 };

function Calibration() {
  const { apiKey } = useApp();
  const { toast } = useToast();
  const act = useAction(() => api.calibration(apiKey || undefined));
  const r: CalibrationResult | null = act.data;
  const run = async () => {
    const res = await act.run();
    if (res) toast("success", "Calibration complete");
  };
  const low = r && (r.helpfulness_agreement < 0.75 || r.tone_agreement < 0.75);

  return (
    <Card
      title="1. Judge calibration"
      icon={<Scale size={16} />}
      subtitle="Before trusting the LLM judge on new cases, check it agrees with our own hand-labelled scores on a small, clear-cut set."
      action={<Button variant="primary" icon={<Play size={15} />} loading={act.loading} onClick={run}>Run calibration</Button>}
    >
      {act.loading && <div className="stack"><div className="row muted small"><Spinner /> Scoring calibration set with the judge...</div><SkeletonCard lines={3} /></div>}
      {act.error && <ErrorBox error={act.error} onRetry={run} />}
      {r && !act.loading && (
        <div className="stack">
          <div className="grid c2">
            <Stat label="Helpfulness agreement" value={pct(r.helpfulness_agreement)} accent="good" />
            <Stat label="Tone agreement" value={pct(r.tone_agreement)} accent="cyan" />
          </div>
          {low && <Notice>Judge agreement is below 75% - treat its scores with caution.</Notice>}
          <DataTable
            columns={["question", "human_help", "judge_help", "help_agree", "human_tone", "judge_tone", "tone_agree", "judge_reasoning"]}
            rows={r.rows.map((x) => ({
              question: x.question, human_help: x.human_helpfulness, judge_help: x.judge.helpfulness, help_agree: x.helpfulness_agree,
              human_tone: x.human_tone, judge_tone: x.judge.tone, tone_agree: x.tone_agree, judge_reasoning: x.judge.reasoning,
            }))}
            render={{
              help_agree: (v) => <Badge kind={v ? "success" : "danger"}>{v ? "agree" : "differ"}</Badge>,
              tone_agree: (v) => <Badge kind={v ? "success" : "danger"}>{v ? "agree" : "differ"}</Badge>,
            }}
          />
        </div>
      )}
      {!r && !act.loading && !act.error && <div className="faint small">Not run yet.</div>}
    </Card>
  );
}

function Regression() {
  const { apiKey } = useApp();
  const { toast } = useToast();
  const act = useAction(() => api.regression(apiKey || undefined));
  const r: RegressionResult | null = act.data;
  const run = async () => {
    const res = await act.run();
    if (res) toast("success", "Regression suite finished");
  };

  // Try to chart before/after numeric columns in the summary table.
  let chart: { rows: Record<string, unknown>[]; label: string; keys: string[] } | null = null;
  if (r && r.summary.length) {
    const cols = Object.keys(r.summary[0]);
    const label = cols.find((c) => typeof r.summary[0][c] === "string");
    const keys = cols.filter((c) => typeof r.summary[0][c] === "number" && /before|after/i.test(c));
    if (label && keys.length) chart = { rows: r.summary, label, keys };
  }

  return (
    <Card
      title="2. Before/after regression on real trace failures"
      icon={<GitCompareArrows size={16} />}
      subtitle={'Each row is a real query that produced a bad answer in production. "Before" replays the old, buggy rerank fallback (collapses to 1 document); "after" uses the current pipeline. Takes about a minute.'}
      action={<Button variant="primary" icon={<Play size={15} />} loading={act.loading} onClick={run}>Run regression suite</Button>}
    >
      {act.loading && <div className="stack"><div className="row muted small"><Spinner /> Running retrieval + rerank + judge for each case. This is slow...</div><SkeletonCard lines={4} /></div>}
      {act.error && <ErrorBox error={act.error} onRetry={run} />}
      {r && !act.loading && (
        <div className="stack">
          {chart && (
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={chart.rows as any[]}>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis dataKey={chart.label} stroke="var(--text-3)" fontSize={12} />
                  <YAxis stroke="var(--text-3)" fontSize={12} />
                  <Tooltip contentStyle={CHART_TIP} cursor={{ fill: "var(--surface-2)" }} />
                  <Legend />
                  {chart.keys.map((k, i) => <Bar key={k} dataKey={k} fill={/before/i.test(k) ? "#fb7185" : "#34d399"} radius={[6, 6, 0, 0]} animationDuration={900 + i * 200} />)}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <b className="small">Score per problem type (before to after)</b>
          <DataTable rows={r.summary} />
          <b className="small">Per-case detail</b>
          <DataTable rows={r.rows} />
        </div>
      )}
      {!r && !act.loading && !act.error && <div className="faint small">Not run yet.</div>}
    </Card>
  );
}

function Ratings() {
  const [ratings, setRatings] = useState<Rating[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setError(null);
    setRatings(null);
    api.listRatings().then(setRatings).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  const n = ratings?.length ?? 0;
  const agree = (a: "judge_helpfulness" | "judge_tone", b: "human_helpfulness" | "human_tone") =>
    (ratings ?? []).filter((r) => r[a] != null && Math.abs((r[a] as number) - (r[b] as number)) <= 1).length;

  return (
    <Card
      title="3. Your ratings so far"
      icon={<Star size={16} />}
      subtitle={'Ratings saved from the chat page\'s "Rate this answer" flow.'}
      action={<Button size="sm" variant="ghost" icon={<RefreshCw size={14} />} onClick={load}>Refresh</Button>}
    >
      {error && <ErrorBox error={error} onRetry={load} />}
      {!ratings && !error && <SkeletonCard lines={3} />}
      {ratings && n === 0 && <EmptyState title="No ratings yet" icon={<Star size={28} />}>Ask a question on the Chat page and use "Rate this answer".</EmptyState>}
      {ratings && n > 0 && (
        <div className="stack">
          <div className="grid c3">
            <Stat label="Ratings" value={n} accent="violet" />
            <Stat label="You vs judge: helpfulness" value={pct(agree("judge_helpfulness", "human_helpfulness") / n)} accent="good" hint="within 1 point" />
            <Stat label="You vs judge: tone" value={pct(agree("judge_tone", "human_tone") / n)} accent="cyan" hint="within 1 point" />
          </div>
          <DataTable rows={ratings.map((r) => ({ ...r, contexts: undefined }))} columns={["query_id", "question", "answer", "judge_helpfulness", "judge_tone", "human_helpfulness", "human_tone", "note"]} />
        </div>
      )}
    </Card>
  );
}

export default function EvaluationPage() {
  return (
    <>
      <PageHero icon={<FlaskConical size={28} />} title="Evaluation">
        Permanent regression tests built from real production failures, scored with cheap rule checks first and an LLM judge for what rules cannot decide (tone, helpfulness).
      </PageHero>
      <div className="stack"><Calibration /><Regression /><Ratings /></div>
    </>
  );
}
