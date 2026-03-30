export interface PromptTemplate {
  id: string;
  name: string;
  description: string;
  template: string;
  variables: string[];
  domain_pack: string;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DomainPackVersion {
  id: string;
  pack_name: string;
  version: string;
  description: string;
  prompt_count: number;
  rule_count: number;
  schema_count: number;
  is_active: boolean;
  published_at: string;
  created_at: string;
}

export interface ModelRun {
  id: string;
  model_name: string;
  provider: string;
  workflow_type: string;
  case_id: string;
  prompt_template_id: string | null;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  status: "success" | "error" | "timeout";
  error_message: string | null;
  created_at: string;
}

export interface EvalCase {
  id: string;
  eval_run_id: string;
  case_id: string;
  expected: Record<string, unknown>;
  actual: Record<string, unknown>;
  metrics: Record<string, number>;
  passed: boolean;
  notes: string | null;
}

export interface EvalRun {
  id: string;
  name: string;
  description: string;
  domain_pack: string;
  workflow_type: string;
  model_name: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  avg_latency_ms: number;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  cases?: EvalCase[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
