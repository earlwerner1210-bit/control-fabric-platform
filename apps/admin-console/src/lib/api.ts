import axios from "axios";
import type {
  PromptTemplate,
  DomainPackVersion,
  ModelRun,
  EvalRun,
  PaginatedResponse,
} from "./types";

const client = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

// ── Prompt Templates ───────────────────────────────────────────────────

export async function listPromptTemplates(): Promise<PromptTemplate[]> {
  const { data } = await client.get<PromptTemplate[]>("/admin/prompts");
  return data;
}

export async function getPromptTemplate(id: string): Promise<PromptTemplate> {
  const { data } = await client.get<PromptTemplate>(`/admin/prompts/${id}`);
  return data;
}

export async function updatePromptTemplate(
  id: string,
  update: { template?: string; description?: string; is_active?: boolean }
): Promise<PromptTemplate> {
  const { data } = await client.patch<PromptTemplate>(`/admin/prompts/${id}`, update);
  return data;
}

// ── Domain Packs ───────────────────────────────────────────────────────

export async function listDomainPackVersions(): Promise<DomainPackVersion[]> {
  const { data } = await client.get<DomainPackVersion[]>("/admin/domain-packs");
  return data;
}

// ── Model Runs ─────────────────────────────────────────────────────────

export async function listModelRuns(
  page: number = 1,
  filters?: { model_name?: string; status?: string; workflow_type?: string }
): Promise<PaginatedResponse<ModelRun>> {
  const { data } = await client.get<PaginatedResponse<ModelRun>>("/admin/model-runs", {
    params: { page, ...filters },
  });
  return data;
}

// ── Evals ──────────────────────────────────────────────────────────────

export async function listEvalRuns(): Promise<EvalRun[]> {
  const { data } = await client.get<EvalRun[]>("/admin/evals");
  return data;
}

export async function getEvalRun(id: string): Promise<EvalRun> {
  const { data } = await client.get<EvalRun>(`/admin/evals/${id}`);
  return data;
}

export async function triggerEvalRun(input: {
  name: string;
  domain_pack: string;
  workflow_type: string;
  model_name: string;
}): Promise<EvalRun> {
  const { data } = await client.post<EvalRun>("/admin/evals", input);
  return data;
}
