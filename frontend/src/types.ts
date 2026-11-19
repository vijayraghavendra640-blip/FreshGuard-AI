export type Verdict = 'Verified' | 'Stale / Outdated' | 'Needs Review';
export type OverallVerdict = Verdict | 'No Verifiable Claims';

export interface VettingInfo {
  stance: string;
  reliability: string;
  reason: string;
}

export interface Source {
  id: string;
  title: string;
  url: string;
  domain: string;
  snippet: string;
  published_date: string | null;
  days_old: number | null;
  authority_tier: 'primary' | 'secondary' | 'low' | 'none';
  tavily_score?: number;
  provider?: string;
  vetting?: VettingInfo;
}

export interface RejectedSource {
  title: string;
  url: string;
  domain: string;
  reason: string;
  rejected_by: string;
}

export interface TraceStep {
  agent: string;
  step: string;
  status: 'ok' | 'warn' | 'fail' | 'info';
  detail: string;
  at?: number;
  model?: string;
}

export interface ScoreBreakdown {
  authority: number;
  recency: number;
  corroboration: number;
  grounding: number;
}

export interface ClaimResult {
  id: string;
  claim: string;
  source_sentence: string;
  category: string;
  time_sensitive: boolean;
  freshness_reason: string;
  verdict: Verdict;
  freshness_score: number;
  evidence_strength: number;
  score_breakdown: ScoreBreakdown;
  confidence: number;
  explanation: string;
  current_fact: string;
  corrected_statement: string;
  evidence_quote: string;
  quote_verified: boolean;
  cited_source: Source | null;
  sources: Source[];
  rejected_sources: RejectedSource[];
  tavily_answer: string;
  search_queries: { round: number; query: string; topic: string; search_depth: string; results: number; cached: boolean }[];
  vetting_method: string;
  audit: { status: 'passed' | 'partial' | 'failed' | 'not_run'; issues: string[]; withheld?: boolean };
  verification_attempts: number;
  models: { verifier?: string; auditor?: string };
  agent_trace: TraceStep[];
  cached: boolean;
}

export interface Report {
  report_id: string;
  analyzed_text: string;
  overall_verdict: OverallVerdict;
  overall_score: number | null;
  risk_level: string;
  total_claims: number;
  verified_count: number;
  stale_count: number;
  needs_review_count: number;
  time_sensitive_count: number;
  summary: string;
  claims: ClaimResult[];
  pipeline: {
    extraction: { method: string; model: string; attempts: number; rejected_claims: { claim: string; reason: string }[] };
    tavily_searches: number;
    bifrost_calls: number;
    gateway: { base_url: string; primary_model: string; fallback_models: string[]; auditor_model: string };
  };
  warnings: string[];
  latency_ms: number;
  timestamp: string;
  engine_version: string;
}

export interface PendingClaim {
  id: string;
  claim: string;
  category: string;
  time_sensitive: boolean;
}

export type Stage = 'idle' | 'extracting' | 'verifying' | 'done' | 'error';

export type StreamEvent =
  | { type: 'stage'; stage: Stage; detail: string }
  | { type: 'claims'; claims: PendingClaim[]; extraction: { method: string; model: string } }
  | { type: 'claim_step'; claim_id: string; step: TraceStep }
  | { type: 'claim_result'; claim: ClaimResult }
  | { type: 'report'; report: Report }
  | { type: 'error'; status: number; detail: string }
  | { type: 'done' };

export interface Preset {
  id: string;
  title: string;
  category: string;
  description: string;
  prompt: string;
  text: string;
}

