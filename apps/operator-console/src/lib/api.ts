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
