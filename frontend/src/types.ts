// Mirrors revenue_recovery.domain.results.PipelineReport (JSON shape).

export type DiagnosisMethod = "rule" | "llm" | "llm_fallback" | "unhandled";
export type DiagnosisAction =
  | "retry_now"
  | "retry_later"
  | "request_update"
  | "send_reminder"
  | "do_not_contact";
export type ExecutionMethod =
  | "razorpay_api"
  | "razorpay_order"
  | "razorpay_api_simulated"
  | "razorpay_api_ratelimited"
  | "llm_message"
  | "template_message"
  | "blocked"
  | "unhandled"
  | "pipeline_error";
export type RecoveryOutcome = "recovered" | "not_recovered" | "pending" | "n/a";

export interface Diagnosis {
  transaction_id: string;
  root_cause: string;
  action: DiagnosisAction;
  method: DiagnosisMethod;
  confidence: number;
  reasoning: string;
  model_name: string | null;
  latency_ms: number | null;
}

export interface RecoveryDecision {
  transaction_id: string;
  customer_id: string;
  diagnosis_action: DiagnosisAction;
  final_action: DiagnosisAction | null;
  blocked: boolean;
  reason: string;
  strategy: string;
  scheduled_for: string | null;
}

export interface AuditLogEntry {
  transaction_id: string;
  customer_id: string;
  amount: number;
  diagnosis_method: DiagnosisMethod;
  diagnosis_action: DiagnosisAction;
  final_action: DiagnosisAction | null;
  executed: boolean;
  execution_method: ExecutionMethod;
  projected_outcome: RecoveryOutcome;
  confirmed_outcome: RecoveryOutcome;
  detail: string;
  reason: string;
  payment_link_id: string | null;
  scheduled_for: string | null;
  recorded_at: string;
}

export interface TransactionResult {
  transaction_id: string;
  stage_reached: "completed" | "failed";
  diagnosis: Diagnosis | null;
  decision: RecoveryDecision | null;
  audit_entry: AuditLogEntry;
  error: string | null;
}

export interface DiagnosisSplit {
  rule: number;
  llm: number;
  llm_fallback: number;
  unhandled: number;
}

export interface RunSummary {
  total_transactions: number;
  needing_attention: number;
  completed: number;
  failed: number;
  executed_actions: number;
  blocked_actions: number;
  escalated_actions: number;
  at_risk: number;
  projected_recovered: number;
  confirmed_recovered: number;
  recovery_rate: number;
  compliance_violations: number;
  diagnosis_split: DiagnosisSplit;
  execution_methods: Record<string, number>;
  action_breakdown: Record<string, number>;
}

export interface PipelineReport {
  run_id: string;
  seed: number;
  count: number;
  failure_injected: boolean;
  started_at: string;
  finished_at: string;
  razorpay_live: boolean;
  anthropic_live: boolean;
  llm_model: string | null;
  results: TransactionResult[];
  summary: RunSummary;
  duration_ms: number;
}

export interface RunRequest {
  count: number;
  seed: number;
  inject_failure: boolean;
}
