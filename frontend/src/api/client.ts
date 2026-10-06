// Single typed client for the FastAPI backend. All calls go through `/api/*`
// (Vite proxies and strips the prefix).

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/* ------------------------------- types ------------------------------- */

export interface Health {
  status: string;
  groq_key_configured: boolean;
}

export interface IngestResult {
  pdf_hash: string;
  filename: string;
  n_chunks: number;
  from_cache: boolean;
  duration_ms: number;
}

export type QualityLabel = "strong_match" | "weak_match" | "no_relevant_match";

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number | null;
}

export interface QueryResult {
  query_id: string;
  query: string;
  answer: string;
  reasoning?: string | null;
  issues: { stage: string; type: string; detail: string }[];
  status: string;
  total_duration_ms: number;
  steps: {
    retrieve: { duration_ms: number; top_k?: number; docs_retrieved?: number; documents_preview?: string[] };
    rerank: { duration_ms: number; docs_after_rerank?: number; top_score?: number | null; documents?: { text: string; score: number }[] };
    generate: { duration_ms: number; answer?: string; reasoning?: string; usage?: Usage };
  };
  contexts: string[];
  quality_signal: {
    top_rerank_score: number | null;
    docs_passed_positive_threshold: number;
    docs_returned: number;
    label: QualityLabel;
  };
  usage: Usage | null;
  cache: { hit: boolean; similarity?: number; matched_query?: string; age_s?: number; saved_cost_usd?: number } | null;
}

export interface JudgeResult {
  rules: { source_present: boolean; [k: string]: unknown };
  judge: { helpfulness: number; tone: number; reasoning: string; [k: string]: unknown };
}

export interface RatingInput {
  query_id: string;
  question: string;
  answer: string;
  contexts: string[];
  judge_helpfulness?: number | null;
  judge_tone?: number | null;
  judge_reasoning?: string | null;
  human_helpfulness: number;
  human_tone: number;
  note?: string | null;
}

export interface Rating extends RatingInput {
  [k: string]: unknown;
}

export interface CalibrationResult {
  helpfulness_agreement: number;
  tone_agreement: number;
  rows: {
    question: string;
    human_helpfulness: number;
    human_tone: number;
    helpfulness_agree: boolean;
    tone_agree: boolean;
    judge: { helpfulness: number; tone: number; reasoning: string };
  }[];
}

export interface RegressionResult {
  rows: Record<string, unknown>[];
  summary: Record<string, unknown>[];
}

export interface ToolLogEntry {
  iteration: number;
  tool: string;
  args?: unknown;
  result?: unknown;
  question?: string;
  answer?: string;
  quality?: string;
  error?: string | null;
  latency_ms?: number;
}

export interface DocumentAgentResult {
  question?: string;
  answer: string;
  status: string;
  budget_exceeded: string | null;
  tool_log: ToolLogEntry[];
  iterations_used: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number;
}

export interface Claim {
  claim_id: string;
  claimant: string;
  claim_type: string;
  status: string;
  reported_amount: number;
  deductible: number;
  adjuster_notes: string;
  expected_disposition: string;
  expected_payout: number;
  [k: string]: unknown;
}

export interface ClaimRun {
  claim_id?: string;
  status: string;
  passed: boolean;
  disposition: string | null;
  payout: number | null;
  iterations_used: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number;
  budget_exceeded: string | null;
  tool_log: ToolLogEntry[];
  guard_events?: { type: string; peril?: string; [k: string]: unknown }[];
  attack_succeeded?: boolean;
}

export interface RaceSummary {
  pass_rate: number;
  p50_latency_ms: number;
  total_tokens: number;
  cost_per_claim: number;
}

export interface RaceResult {
  claims: Claim[];
  agent: ClaimRun[];
  workflow: ClaimRun[];
  agent_summary: RaceSummary;
  workflow_summary: RaceSummary;
}

export interface TrajectoryRow {
  claim_id: string;
  guarded: boolean;
  status: string;
  passed: boolean;
  expected_trajectory: string;
  actual_trajectory: string;
  trajectory_match: boolean;
  outcome_vs_trajectory_gap: boolean;
  guard_events: unknown[];
}

export interface TrajectorySummary {
  outcome_pass_rate: number;
  tool_choice_accuracy: number;
  gap_count: number;
  gap_claims: string[];
}

export interface TrajectoryResult {
  max_iterations: number;
  before: TrajectoryRow[];
  after: TrajectoryRow[];
  before_summary: TrajectorySummary;
  after_summary: TrajectorySummary;
  expected: Record<string, string[]>;
  claims: Claim[];
}

export interface InjectionResult {
  claim: Claim;
  before: ClaimRun;
  after: ClaimRun;
}

export interface McpTool {
  name: string;
  description: string;
  input_schema: {
    type?: string;
    properties?: Record<string, { type?: string; title?: string; description?: string; default?: unknown; anyOf?: { type?: string }[]; enum?: unknown[] }>;
    required?: string[];
  };
}

export interface McpTools {
  server_info: { name: string; protocol_version: string };
  tools: McpTool[];
}

export interface McpCallResult {
  is_error: boolean;
  parsed: any;
  raw_text: string;
  structured_content?: unknown;
}

export interface AgentCard {
  name: string;
  description: string;
  url: string;
  version?: string;
  skills?: { id: string; name: string; description: string }[];
  [k: string]: unknown;
}

export interface A2AQuality {
  label?: string;
  top_rerank_score?: number | null;
  [k: string]: unknown;
}

export interface A2ASpecialist {
  answer: string;
  contexts?: string[];
  quality_signal: A2AQuality;
  [k: string]: unknown;
}

export interface A2AStats {
  quality_label: string;
  latency_ms: number;
  total_tokens: number | null;
  estimated_cost_usd: number | null;
}

export interface A2AResult {
  team: {
    answer: string;
    delegations: Record<string, unknown>[];
    document_answer: A2ASpecialist;
    evidence_review: A2ASpecialist;
  };
  single: { answer: string; contexts?: string[]; quality_signal: A2AQuality };
  metrics: { winner: string; verdict_reason: string; team: A2AStats; single: A2AStats };
}

export interface ObsSummary {
  queries: number;
  errors: number;
  with_issues: number;
  cache_hits: number;
  cache_hit_rate: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost_usd: number;
  saved_cost_usd: number;
  avg_cost_per_llm_call_usd: number | null;
  latency_ms: { p50: number | null; p95: number | null; avg_cache_hit: number | null; avg_cache_miss: number | null };
  stage_avg_ms: Record<string, number | null>;
  issue_counts: Record<string, number>;
  alerts: number;
}

export interface ObsQuery {
  ts: string;
  query_id: string;
  query?: string;
  status?: string;
  cache_hit?: boolean;
  total_ms?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  cost_usd?: number;
  top_score?: number | null;
  issues?: unknown;
  alerts?: unknown;
  [k: string]: unknown;
}

export interface ObsFailure {
  query_id: string;
  status: string;
  kinds: string[];
  query?: string;
  answer?: string;
  pdf_hash?: string;
  details?: string[];
  [k: string]: unknown;
}

export interface ObsCase {
  case_id: string;
  problem_type?: string;
  question?: string;
  should_answer?: boolean;
  expected_keyword?: unknown;
  created?: string;
  [k: string]: unknown;
}

export interface ObsCache {
  enabled?: boolean;
  entries: number;
  threshold: number;
  ttl_s: number;
  max_entries?: number;
  namespaces?: Record<string, number>;
}

/* ------------------------------ plumbing ------------------------------ */

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: any) => (d?.msg ? `${(d.loc || []).slice(1).join(".")}: ${d.msg}` : JSON.stringify(d))).join("; ");
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    throw new ApiError("Cannot reach the backend. Is it running on http://localhost:8000?", 0);
  }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      const d = formatDetail(body?.detail);
      if (d) msg = d;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(msg, res.status);
  }
  return (await res.json()) as T;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

const keyBody = (key?: string) => (key ? { groq_api_key: key } : {});

/* ------------------------------- calls -------------------------------- */

export const api = {
  health: () => request<Health>("/health"),

  ingest(file: File, key?: string) {
    const fd = new FormData();
    fd.append("file", file);
    if (key) fd.append("groq_api_key", key);
    return request<IngestResult>("/documents", { method: "POST", body: fd });
  },
  query: (pdf_hash: string, query: string, use_cache = true) =>
    request<QueryResult>("/query", json("POST", { pdf_hash, query, use_cache })),
  judge: (question: string, contexts: string[], answer: string, key?: string) =>
    request<JudgeResult>("/judge", json("POST", { question, contexts, answer, ...keyBody(key) })),
  saveRating: (r: RatingInput) => request<{ [k: string]: unknown }>("/ratings", json("POST", r)),
  listRatings: () => request<Rating[]>("/ratings"),

  calibration: (key?: string) => request<CalibrationResult>("/eval/calibration", json("POST", keyBody(key))),
  regression: (key?: string) => request<RegressionResult>("/eval/regression", json("POST", keyBody(key))),

  documentAgent: (pdf_hash: string, question: string) =>
    request<DocumentAgentResult>("/agent/document", json("POST", { pdf_hash, question })),
  claims: () => request<Claim[]>("/agent/claims"),
  claimsRace: () => request<RaceResult>("/agent/claims/race", json("POST", {})),
  claimsTrajectory: () => request<TrajectoryResult>("/agent/claims/trajectory", json("POST", {})),
  claimsInjection: () => request<InjectionResult>("/agent/claims/injection", json("POST", {})),

  mcpTools: () => request<McpTools>("/mcp/tools"),
  mcpCall: (name: string, args: Record<string, unknown>) =>
    request<McpCallResult>("/mcp/call", json("POST", { name, arguments: args })),

  a2aAgents: () => request<AgentCard[]>("/a2a/agents"),
  async a2aRace(pdf_hash: string, question: string): Promise<A2AResult> {
    const id = crypto.randomUUID().replace(/-/g, "");
    const rpc = await request<any>("/a2a/manager", json("POST", {
      jsonrpc: "2.0",
      id,
      method: "message/send",
      params: {
        message: {
          kind: "message",
          messageId: crypto.randomUUID().replace(/-/g, ""),
          role: "user",
          parts: [{ kind: "text", text: JSON.stringify({ pdf_hash, question }) }],
        },
      },
    }));
    if (rpc.error) throw new ApiError(`A2A manager failed: ${rpc.error.message ?? "unknown error"}`, 500);
    const parts: string[] = (rpc.result?.artifacts ?? [])
      .flatMap((a: any) => a.parts ?? [])
      .filter((p: any) => p.kind === "text")
      .map((p: any) => p.text);
    if (!parts.length) throw new ApiError("A2A manager returned no result artifact.", 500);
    const result = JSON.parse(parts[0]);
    if (!result.team || !result.single || !result.metrics) throw new ApiError("A2A manager returned an incomplete race result.", 500);
    return result as A2AResult;
  },

  obsSummary: () => request<ObsSummary>("/observability/summary"),
  obsQueries: (limit = 200) => request<ObsQuery[]>(`/observability/queries?limit=${limit}`),
  obsFailures: (status?: string) => request<ObsFailure[]>(`/observability/failures${status ? `?status=${status}` : ""}`),
  obsCases: () => request<ObsCase[]>("/observability/cases"),
  obsCache: () => request<ObsCache>("/observability/cache"),
  obsClearCache: () => request<{ removed: number }>("/observability/cache", { method: "DELETE" }),
  obsPromote: (id: string, should_answer: boolean, expected_keyword: string | null, problem_type: string | null) =>
    request<ObsCase>(`/observability/failures/${encodeURIComponent(id)}/promote`, json("POST", {
      should_answer,
      expected_keyword: expected_keyword || null,
      problem_type: problem_type || null,
    })),
};
