import axios from "axios";
import type {
  Document,
  WorkflowCase,
  AuditEvent,
  ValidationResult,
  ControlObject,
  ContractCompileInput,
  WorkOrderReadinessInput,
  IncidentDispatchInput,
  MarginDiagnosisInput,
  PaginatedResponse,
} from "./types";

const client = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

// ── Documents ──────────────────────────────────────────────────────────

export async function uploadDocument(file: File): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<Document>("/documents/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function parseDocument(id: string): Promise<Document> {
  const { data } = await client.post<Document>(`/documents/${id}/parse`);
  return data;
}

export async function embedDocument(id: string): Promise<Document> {
  const { data } = await client.post<Document>(`/documents/${id}/embed`);
  return data;
}

export async function listDocuments(
  page: number = 1,
  pageSize: number = 20
): Promise<PaginatedResponse<Document>> {
  const { data } = await client.get<PaginatedResponse<Document>>("/documents", {
    params: { page, page_size: pageSize },
  });
  return data;
}

// ── Workflows ──────────────────────────────────────────────────────────

export async function triggerContractCompile(
  input: ContractCompileInput
): Promise<WorkflowCase> {
  const { data } = await client.post<WorkflowCase>("/workflows/contract-compile", input);
  return data;
}

export async function triggerWorkOrderReadiness(
  input: WorkOrderReadinessInput
): Promise<WorkflowCase> {
  const { data } = await client.post<WorkflowCase>("/workflows/work-order-readiness", input);
  return data;
}

export async function triggerIncidentDispatch(
  input: IncidentDispatchInput
): Promise<WorkflowCase> {
  const { data } = await client.post<WorkflowCase>("/workflows/incident-dispatch", input);
  return data;
}

export async function triggerMarginDiagnosis(
  input: MarginDiagnosisInput
): Promise<WorkflowCase> {
  const { data } = await client.post<WorkflowCase>("/workflows/margin-diagnosis", input);
  return data;
}

// ── Cases ──────────────────────────────────────────────────────────────

export async function getCase(caseId: string): Promise<WorkflowCase> {
  const { data } = await client.get<WorkflowCase>(`/cases/${caseId}`);
  return data;
}

export async function getCaseAudit(caseId: string): Promise<AuditEvent[]> {
  const { data } = await client.get<AuditEvent[]>(`/cases/${caseId}/audit`);
  return data;
}

export async function getCaseValidations(caseId: string): Promise<ValidationResult[]> {
  const { data } = await client.get<ValidationResult[]>(`/cases/${caseId}/validations`);
  return data;
}

export async function getCaseControlObjects(caseId: string): Promise<ControlObject[]> {
  const { data } = await client.get<ControlObject[]>(`/cases/${caseId}/control-objects`);
  return data;
}

export async function listCases(
  page: number = 1,
  status?: string,
  workflow?: string
): Promise<PaginatedResponse<WorkflowCase>> {
  const { data } = await client.get<PaginatedResponse<WorkflowCase>>("/cases", {
    params: { page, status, workflow_type: workflow },
  });
  return data;
}
