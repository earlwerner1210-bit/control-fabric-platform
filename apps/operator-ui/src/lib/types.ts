// ── Enums ──────────────────────────────────────────────────────────────

export type WorkflowStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type CaseVerdict = "approved" | "rejected" | "needs_review" | "escalated";
export type ReadinessVerdict = "ready" | "blocked" | "warn" | "escalate";
export type MarginVerdict = "billable" | "non_billable" | "under_recovery" | "penalty_risk" | "unknown";
export type ValidationStatus = "passed" | "warned" | "blocked" | "escalated";
export type ValidationSeverity = "info" | "warning" | "error" | "critical";
export type ControlObjectType =
  | "obligation"
  | "billable_event"
  | "penalty_condition"
  | "dispatch_precondition"
  | "skill_requirement"
  | "incident_state"
  | "escalation_rule"
  | "service_state"
  | "readiness_check"
  | "leakage_trigger";

// ── Documents ──────────────────────────────────────────────────────────

export interface Document {
  id: string;
  tenant_id: string;
  filename: string;
  content_type: string;
  s3_key: string;
  size_bytes: number;
  checksum: string;
  page_count: number | null;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  page_number: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

// ── Control Objects ────────────────────────────────────────────────────

export interface ControlObject {
  id: string;
  tenant_id: string;
  control_type: ControlObjectType;
  label: string;
  description: string | null;
  payload: Record<string, unknown>;
  source_document_id: string | null;
  source_chunk_id: string | null;
  confidence: number | null;
  is_active: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ControlLink {
  id: string;
  tenant_id: string;
  source_id: string;
  target_id: string;
  relation_type: string;
  weight: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// ── Workflow Case ──────────────────────────────────────────────────────

export interface WorkflowCase {
  id: string;
  tenant_id: string;
  workflow_type: string;
  status: WorkflowStatus;
  verdict: CaseVerdict | null;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown> | null;
  error_detail: string | null;
  started_at: string | null;
  completed_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// ── Validation ─────────────────────────────────────────────────────────

export interface ValidationRuleResult {
  rule_name: string;
  passed: boolean;
  message: string;
  severity: ValidationSeverity;
  metadata: Record<string, unknown>;
}

export interface ValidationResult {
  id: string;
  tenant_id: string;
  target_type: string;
  target_id: string;
  status: string;
  rules_passed: number;
  rules_warned: number;
  rules_blocked: number;
  rule_results: ValidationRuleResult[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// ── Audit ──────────────────────────────────────────────────────────────

export interface AuditEvent {
  id: string;
  tenant_id: string;
  event_type: string;
  actor_id: string | null;
  resource_type: string;
  resource_id: string;
  action: string;
  detail: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

// ── Workflow Inputs / Outputs ──────────────────────────────────────────

export interface ContractCompileInput {
  document_id: string;
  domain_pack?: string;
  extract_obligations?: boolean;
  extract_penalties?: boolean;
  extract_billing?: boolean;
}

export interface ContractCompileOutput {
  document_id: string;
  control_object_ids: string[];
  entity_ids: string[];
  warnings: string[];
  summary: string | null;
}

export interface WorkOrderReadinessInput {
  work_order_id: string;
  control_object_ids?: string[];
  required_skills?: string[];
  dispatch_region?: string;
}

export interface WorkOrderReadinessOutput {
  work_order_id: string;
  verdict: ReadinessVerdict;
  blockers: string[];
  warnings: string[];
  matched_skills: string[];
  missing_skills: string[];
}

export interface IncidentDispatchInput {
  incident_id: string;
  severity: number;
  category: string;
  region?: string;
  description?: string;
}

export interface IncidentDispatchOutput {
  incident_id: string;
  assigned_team: string | null;
  escalation_level: number;
  recommended_actions: string[];
  sla_target_minutes: number | null;
}

export interface MarginDiagnosisInput {
  billing_record_id: string;
  contract_id?: string;
  line_items?: Record<string, unknown>[];
  period_start?: string;
  period_end?: string;
}

export interface MarginDiagnosisOutput {
  billing_record_id: string;
  verdict: MarginVerdict;
  leakage_amount: number | null;
  leakage_reasons: string[];
  matched_obligations: string[];
  recommendations: string[];
}

// ── Pagination ─────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
