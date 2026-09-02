// Mirrors recover_ai.domain.results.PipelineReport (JSON shape).

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
  | "pipeline_error"
  | "holdout_control"
  | "retry_held_incident"
  | "skipped_negative_ev"
  | "shadow";
export type RecoveryOutcome = "recovered" | "not_recovered" | "pending" | "n/a";
export type Channel = "payment_link" | "in_app" | "email" | "sms" | "whatsapp";

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
  policy_version: string | null;
  conversion_key: string | null;
  predicted_rate: number | null;
  net_expected_value: number | null;
  channel: Channel | null;
  channel_cost: number | null;
  held_out: boolean;
  idempotency_key: string | null;
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

export interface CausalLift {
  holdout_fraction: number;
  treatment_n: number;
  control_n: number;
  treatment_rate: number;
  control_rate: number;
  incremental_rate: number;
}

export interface Economics {
  total_channel_cost: number;
  net_expected_value: number;
  skipped_negative_ev: number;
  positive_ev_actions: number;
  channel_mix: Record<string, number>;
}

export interface RunSummary {
  total_transactions: number;
  needing_attention: number;
  completed: number;
  failed: number;
  executed_actions: number;
  blocked_actions: number;
  escalated_actions: number;
  held_out_actions: number;
  retries_held_incident: number;
  at_risk: number;
  projected_recovered: number;
  confirmed_recovered: number;
  recovery_rate: number;
  compliance_violations: number;
  diagnosis_split: DiagnosisSplit;
  execution_methods: Record<string, number>;
  action_breakdown: Record<string, number>;
  causal: CausalLift;
  economics: Economics;
}

export interface IncidentRecord {
  reason: string;
  method: string;
  count: number;
  share: number;
  window_minutes: number;
  action_taken: string;
}

export interface ConversionRate {
  action: string;
  method: string;
  reason: string;
  amount_band: string;
  rate: number;
  ci_low: number;
  ci_high: number;
  observations: number;
}

export interface CalibrationRow {
  bucket: string;
  predicted: number;
  observed: number;
  n: number;
}

export interface ExperimentLift {
  treatment_rate: number;
  control_rate: number;
  treatment_n: number;
  control_n: number;
  incremental_rate: number;
  ci_low: number;
  ci_high: number;
}

export interface LearningSummary {
  policy_version: string;
  conversion_rates: ConversionRate[];
  brier_score: number;
  calibration_table: CalibrationRow[];
  observations: number;
  retry_timing_hours: Record<string, number>;
  experiment: ExperimentLift;
}

export interface PipelineReport {
  run_id: string;
  seed: number;
  count: number;
  failure_injected: boolean;
  mode: "live" | "shadow";
  policy_version: string;
  started_at: string;
  finished_at: string;
  razorpay_live: boolean;
  anthropic_live: boolean;
  llm_model: string | null;
  results: TransactionResult[];
  summary: RunSummary;
  incidents: IncidentRecord[];
  learning: LearningSummary | null;
  duration_ms: number;
}

export interface RunRequest {
  count: number;
  seed: number;
  inject_failure: boolean;
  mode?: "live" | "shadow";
}
