import { useEffect, useState } from "react";
import { Flag, Play, Bot, Workflow, Trophy } from "lucide-react";
import { api, Claim, ClaimRun, RaceSummary } from "../../api/client";
import { useAction } from "../../lib/useAsync";
import { Card, Button, Stat, Badge, ToolSteps, ErrorBox, SkeletonCard, Collapse, DataTable, Spinner, useToast, EmptyState } from "..";
import { ms, pct, usd } from "../../lib/format";

function SummaryBlock({ title, icon, s, accent }: { title: string; icon: React.ReactNode; s: RaceSummary; accent: string }) {
  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="row" style={{ fontWeight: 700 }}>{icon}{title}</div>
      <div className="grid c2">
        <Stat label="Pass rate" value={pct(s.pass_rate)} accent={accent} />
        <Stat label="p50 latency" value={ms(s.p50_latency_ms)} accent={accent} />
        <Stat label="Total tokens" value={s.total_tokens.toLocaleString()} accent={accent} />
        <Stat label="Cost / claim" value={usd(s.cost_per_claim)} accent={accent} />
      </div>
    </div>
  );
}

function RunCell({ run, label, icon, showBudget }: { run: ClaimRun; label: string; icon: React.ReactNode; showBudget?: boolean }) {
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row" style={{ gap: 8 }}>
        <b className="small row" style={{ gap: 6 }}>{icon}{label}</b>
        <Badge kind={run.passed ? "success" : "danger"}>{run.passed ? "PASS" : "FAIL"}</Badge>
      </div>
      <ToolSteps tools={run.tool_log} blocked={showBudget && run.status === "budget_exceeded" ? `budget: ${run.budget_exceeded}` : null} />
      <div className="faint small">
        disposition=<b>{String(run.disposition)}</b> payout=<b>{String(run.payout)}</b> - {run.iterations_used} iters - {run.total_tokens} tokens - {usd(run.cost_usd)} - {ms(run.latency_ms)}
      </div>
    </div>
  );
}

export function ClaimsRaceTab() {
  const { toast } = useToast();
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [claimsErr, setClaimsErr] = useState<string | null>(null);
  const act = useAction(() => api.claimsRace());

  useEffect(() => {
    api.claims().then(setClaims).catch((e) => setClaimsErr(e.message));
  }, []);

  const run = async () => {
    const r = await act.run();
    if (r) toast("success", "Race finished", `${r.claims.length} claims triaged by both systems`);
  };
  const r = act.data;

  return (
    <div className="stack">
      <Card
        title="Agent vs fixed workflow"
        icon={<Flag size={16} />}
        subtitle="A budgeted claims-triage agent vs. a fixed workflow - same 3 tools, same model, same claims. See which tools each system called and where the agent's iteration budget cuts it off."
        action={<Button variant="primary" icon={<Play size={15} />} loading={act.loading} onClick={run}>Run the race</Button>}
      >
        {act.loading && (
          <div className="row muted small"><Spinner /> Triaging {claims?.length ?? 10} claims with both systems - this takes a few minutes...</div>
        )}
        {claimsErr && <ErrorBox error={claimsErr} />}
      </Card>

      {act.error && <ErrorBox error={act.error} onRetry={run} />}

      {r && !act.loading && (
        <>
          <Card title="Race result - 4 numbers per system" icon={<Trophy size={16} />} glow>
            <div className="grid c2">
              <SummaryBlock title="Agent" icon={<Bot size={16} />} s={r.agent_summary} accent="violet" />
              <SummaryBlock title="Workflow" icon={<Workflow size={16} />} s={r.workflow_summary} accent="cyan" />
            </div>
          </Card>
          <div className="stack stagger">
            {r.claims.map((c, i) => (
              <Card key={c.claim_id} hover>
                <div className="row" style={{ marginBottom: 4 }}>
                  <b>{c.claim_id}</b><span className="muted">{c.claimant}</span><Badge kind="violet">{c.claim_type}</Badge>
                </div>
                <div className="faint small" style={{ marginBottom: 12 }}>{c.adjuster_notes}</div>
                <div className="claimrow">
                  <RunCell run={r.agent[i]} label="Agent" icon={<Bot size={14} />} showBudget />
                  <RunCell run={r.workflow[i]} label="Workflow" icon={<Workflow size={14} />} />
                </div>
                <div className="faint xs" style={{ marginTop: 10 }}>Ground truth: disposition={c.expected_disposition} payout={c.expected_payout}</div>
              </Card>
            ))}
          </div>
          <Collapse title="Raw results table">
            <DataTable
              rows={r.claims.flatMap((c, i) =>
                (["agent", "workflow"] as const).map((sys) => {
                  const x = r[sys][i];
                  return { claim_id: c.claim_id, system: sys, passed: x.passed, disposition: x.disposition, payout: x.payout, iterations: x.iterations_used, tokens: x.total_tokens, cost_usd: x.cost_usd, latency_ms: Math.round(x.latency_ms), budget_exceeded: x.budget_exceeded };
                }),
              )}
            />
          </Collapse>
        </>
      )}

      {!r && !act.loading && (
        <>
          {!claims && !claimsErr && <SkeletonCard lines={4} />}
          {claims && (
            <Card title={`${claims.length} synthetic claims ready`} subtitle="Click Run the race to triage them all.">
              <DataTable rows={claims} columns={["claim_id", "claimant", "claim_type", "status", "reported_amount", "deductible", "expected_disposition", "expected_payout"]} />
            </Card>
          )}
          {claims?.length === 0 && <EmptyState title="No claims" />}
        </>
      )}
    </div>
  );
}
