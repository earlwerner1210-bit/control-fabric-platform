// API client — connects to FastAPI backend

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { next: { revalidate: 0 } });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json();
}

export const api = {
  // Reconciliation
  runReconciliation: () => post<ReconciliationRunResult>("/reconciliation/run"),
  getCases: () => get<CaseListResult>("/reconciliation/cases"),
  getCase: (id: string) => get<Case>(`/reconciliation/cases/${id}`),
  resolveCase: (id: string, resolved_by: string, resolution_note: string) =>
    post<{ status: string }>(
      `/reconciliation/cases/${id}/resolve?resolved_by=${encodeURIComponent(resolved_by)}&resolution_note=${encodeURIComponent(resolution_note)}`
    ),
  getRules: () => get<RulesResult>("/reconciliation/rules"),

  // Inference / audit
  getAuditIntegrity: () =>
    get<{ chain_valid: boolean; total_records: number }>(
      "/inference/audit/integrity/verify"
    ),
  getSessionAudit: (id: string) =>
    get<SessionAudit>(`/inference/audit/${id}`),

  // Ingress stats
  getIngressStats: () => get<IngressStats>("/ingress/stats"),

  // Graph
  traverseGraph: (id: string, direction = "both", depth = 3) =>
    get<GraphTraversal>(
      `/graph/traverse/${id}?direction=${direction}&max_depth=${depth}`
    ),
  getImpact: (id: string) => get<ImpactAnalysis>(`/graph/impact/${id}`),
  getObject: (id: string) => get<ControlObject>(`/ingress/objects/${id}`),
  getObjectHistory: (id: string) =>
    get<ObjectHistory>(`/ingress/objects/${id}/history`),

  // Exceptions
  getActiveExceptions: () => get<ExceptionList>("/exceptions/active"),

  // Explainability
  explainBlock: (id: string) => get<BlockExplanation>(`/explain/block/${id}`),
  explainRelease: (id: string) =>
    get<ReleaseExplanation>(`/explain/release/${id}`),
  explainCase: (id: string) => get<CaseExplanation>(`/explain/case/${id}`),
  diffPolicyVersions: (fromId: string, toId: string) =>
    post<PolicyDiff>("/explain/diff-policy-versions", {
      from_version: fromId,
      to_version: toId,
    }),

  // Demo tenant
  resetDemo: () => post<DemoResetResult>("/demo/reset"),
  getDemoScenarios: () => get<DemoScenarioList>("/demo/scenarios"),
  runScenario: (id: string) => post<DemoScenarioResult>(`/demo/scenarios/${id}/run`),
  runAllScenarios: () => post<DemoRunAllResult>("/demo/scenarios/run-all"),

  // Journey
  getJourneySteps: () => get<JourneySteps>("/journey/steps"),
  startJourney: (org: string, user: string) =>
    post<JourneyStartResult>("/journey/start", {
      organisation_name: org,
      created_by: user,
    }),
  journeyConnectSource: (sid: string, name: string, type: string) =>
    post<Record<string, unknown>>(`/journey/${sid}/connect-source`, {
      session_id: sid,
      source_name: name,
      source_type: type,
    }),
  journeyInstallPack: (sid: string) =>
    post<Record<string, unknown>>(`/journey/${sid}/install-pack`),
  journeyApplyDefaults: (sid: string) =>
    post<Record<string, unknown>>(`/journey/${sid}/apply-defaults`),
  journeyIngestSample: (sid: string) =>
    post<Record<string, unknown>>(`/journey/${sid}/ingest-sample`),
  journeyReconcile: (sid: string) =>
    post<Record<string, unknown>>(`/journey/${sid}/reconcile`),
  journeyEvidenceSummary: (sid: string) =>
    get<Record<string, unknown>>(`/journey/${sid}/evidence-summary`),
  journeyDemonstrateGate: (sid: string) =>
    post<Record<string, unknown>>(`/journey/${sid}/demonstrate-gate`),
  journeyAuditReport: (sid: string) =>
    get<Record<string, unknown>>(`/journey/${sid}/audit-report`),

  // Bulk case operations
  bulkAssign: (caseIds: string[], assignee: string) =>
    post<BulkOpResult>("/cases/bulk/assign", {
      case_ids: caseIds,
      assigned_to: assignee,
    }),
  bulkResolve: (caseIds: string[], resolvedBy: string, note: string) =>
    post<BulkOpResult>("/cases/bulk/resolve", {
      case_ids: caseIds,
      resolved_by: resolvedBy,
      resolution_note: note,
    }),
  bulkSuppress: (caseIds: string[], suppressedBy: string, reason: string) =>
    post<BulkOpResult>("/cases/bulk/suppress", {
      case_ids: caseIds,
      suppressed_by: suppressedBy,
      reason: reason,
    }),
  getCaseWorkload: () => get<CaseWorkload>("/cases/workload"),
  getCaseAging: () => get<CaseAging>("/cases/aging"),

  // Reports
  getReport: (reportId: string, window = "30d") =>
    get<ReportResult>(`/reports/${reportId}?window=${window}`),
  getReportSummary: () => get<ReportSummary>("/reports/summary"),
};

// Types
export interface Case {
  case_id: string;
  case_type: "gap" | "conflict" | "orphan" | "duplicate";
  severity: "critical" | "high" | "medium" | "low";
  status: "open" | "under_review" | "resolved" | "accepted_risk";
  title: string;
  description: string;
  affected_objects: string[];
  affected_planes: string[];
  violated_rule_id: string | null;
  missing_relationship_type: string | null;
  remediation_suggestions: string[];
  severity_score: number;
  detected_at: string;
  case_hash: string;
}

export interface CaseListResult {
  open_case_count: number;
  cases: Case[];
}

export interface ReconciliationRunResult {
  total_cases: number;
  open_cases: number;
  new_cases_this_run: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  cases: Case[];
}

export interface RulesResult {
  rule_count: number;
  rules: Array<{
    rule_id: string;
    domain_pack: string;
    rule_name: string;
    description: string;
    source_plane: string;
    target_plane: string;
    required_relationship: string;
    severity: string;
    enabled: boolean;
  }>;
}

export interface IngressStats {
  registry_object_count: number;
  graph_node_count: number;
  graph_edge_count: number;
  active_objects: number;
}

export interface GraphTraversal {
  query_object_id: string;
  discovered_objects: string[];
  discovered_edges: string[];
  depth_reached: number;
  path_count: number;
}

export interface ImpactAnalysis {
  object_id: string;
  object_name: string;
  object_type: string;
  operational_plane: string;
  downstream_objects: string[];
  upstream_objects: string[];
  total_affected_objects: number;
  critical_relationships: Array<{
    edge_id: string;
    type: string;
    source: string;
    target: string;
    enforcement_weight: number;
  }>;
  max_depth_analysed: number;
}

export interface ControlObject {
  object_id: string;
  object_type: string;
  name: string;
  description: string;
  state: string;
  version: number;
  schema_namespace: string;
  operational_plane: string;
  created_at: string;
  updated_at: string;
  object_hash: string;
  provenance: {
    source_system: string;
    source_hash: string;
    ingested_by: string;
    ingested_at: string;
  };
}

export interface ObjectHistory {
  object_id: string;
  version_count: number;
  history: Array<{
    version: number;
    state: string;
    changed_by: string;
    change_reason: string;
    recorded_at: string;
    record_hash: string;
  }>;
}

export interface SessionAudit {
  session_id: string;
  record_count: number;
  records: Array<{
    record_id: string;
    session_id: string;
    final_status: string;
    model_id: string;
    inference_duration_ms: number;
    chain_hash: string;
    created_at: string;
  }>;
}

export interface ExceptionList {
  count: number;
  exceptions: Array<{
    exception_id: string;
    type: string;
    risk: string;
    expires_at: string;
    requested_by: string;
  }>;
}

// Explainability types
export interface GateExplanation {
  gate_name: string;
  outcome: string;
  detail: string;
  is_blocking: boolean;
}

export interface BlockExplanation {
  request_id: string;
  action_type: string;
  origin: string;
  requested_by: string;
  requested_at: string;
  overall_outcome: string;
  blocking_gate: string | null;
  blocking_reason: string | null;
  gates: GateExplanation[];
  missing_evidence: string[];
  violated_policies: string[];
  remediation_steps: string[];
  evidence_provided: string[];
  human_summary: string;
}

export interface ReleaseExplanation {
  package_id: string;
  action_type: string;
  origin: string;
  requested_by: string;
  overall_outcome: string;
  gates_passed: string[];
  evidence_used: string[];
  package_hash: string;
  compiled_at: string;
  human_summary: string;
}

export interface CaseExplanation {
  case_id: string;
  case_type: string;
  severity: string;
  explanation: string;
  affected_planes: string[];
  violated_rule: string;
  remediation: string[];
  what_this_means: string;
  what_to_do_next: string;
}

export interface PolicyDiff {
  from_version: number;
  to_version: number;
  is_breaking_change: boolean;
  newly_blocked_actions: string[];
  newly_unblocked_actions: string[];
  change_summary: string;
  impact: string;
  recommendation: string;
}

// Demo types
export interface DemoResetResult {
  status: string;
  objects: number;
  nodes: number;
  edges: number;
  scenarios_available: number;
}

export interface DemoScenario {
  scenario_id: string;
  title: string;
  description: string;
  expected_outcome: string;
  steps: string[];
}

export interface DemoScenarioList {
  scenarios: DemoScenario[];
}

export interface DemoScenarioResult {
  scenario_id: string;
  title: string;
  expected: string;
  outcome: string;
  passed: boolean;
  [key: string]: unknown;
}

export interface DemoRunAllResult {
  total: number;
  passed: number;
  failed: number;
  results: DemoScenarioResult[];
}

// Journey types
export interface JourneyStep {
  step: number;
  name: string;
  api: string;
  description: string;
}

export interface JourneySteps {
  total_steps: number;
  steps: JourneyStep[];
}

export interface JourneyStartResult {
  session_id: string;
  organisation_name: string;
  current_step: number;
  step_name: string;
  next_step: number;
  next_action: string;
  message: string;
}

// Bulk ops types
export interface BulkOpResult {
  operation: string;
  requested: number;
  succeeded: number;
  failed: number;
  results: Array<{ case_id: string; status: string; error?: string }>;
}

export interface CaseWorkload {
  total_open: number;
  by_severity: Record<string, number>;
  by_assignee: Record<string, number>;
  unassigned: number;
}

export interface CaseAging {
  buckets: Array<{
    label: string;
    count: number;
    oldest_hours: number;
  }>;
}

// Report types
export interface ReportResult {
  report_id: string;
  title: string;
  window: string;
  generated_at: string;
  data: Record<string, unknown>;
}

export interface ReportSummary {
  available_reports: Array<{
    report_id: string;
    title: string;
    description: string;
  }>;
}
