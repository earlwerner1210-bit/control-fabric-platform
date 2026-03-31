const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function rg<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API}/rg${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  // Workspaces
  createWorkspace: (name: string, plan = "starter") =>
    rg("/workspaces", { method: "POST", body: JSON.stringify({ name, plan }) }),
  getMyWorkspace: () => rg("/workspaces/me"),
  inviteMember: (workspaceId: string, email: string, role = "operator") =>
    rg(`/workspaces/${workspaceId}/invite`, {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),
  getMembers: (workspaceId: string) => rg(`/workspaces/${workspaceId}/users`),

  // Onboarding
  getOnboardingStatus: (workspaceId: string) =>
    rg(`/onboarding/status/${workspaceId}`),
  startOnboarding: (workspaceId: string) =>
    rg("/onboarding/start", { method: "POST", body: JSON.stringify({ workspace_id: workspaceId }) }),
  connectGitHub: (workspaceId: string, config: Record<string, string>) =>
    rg("/onboarding/connect/github", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, config }),
    }),
  connectJira: (workspaceId: string, config: Record<string, string>) =>
    rg("/onboarding/connect/jira", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, config }),
    }),
  loadDefaults: (workspaceId: string, profile: string) =>
    rg("/onboarding/load-defaults", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, profile }),
    }),
  completeOnboarding: (workspaceId: string) =>
    rg(`/onboarding/complete/${workspaceId}`, { method: "POST" }),

  // Releases
  createRelease: (data: Record<string, unknown>) =>
    rg("/releases", { method: "POST", body: JSON.stringify(data) }),
  listReleases: (workspaceId: string, status?: string) =>
    rg(`/releases?workspace_id=${workspaceId}${status ? `&status=${status}` : ""}`),
  getRelease: (releaseId: string) => rg(`/releases/${releaseId}`),
  submitRelease: (releaseId: string, workspaceId: string) =>
    rg(`/releases/${releaseId}/submit`, {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId }),
    }),
  cancelRelease: (releaseId: string) =>
    rg(`/releases/${releaseId}/cancel`, { method: "POST" }),
  getReleaseTimeline: (releaseId: string) =>
    rg(`/releases/${releaseId}/timeline`),
  explainRelease: (releaseId: string) => rg(`/releases/${releaseId}/explain`),

  // Evidence
  attachTicket: (releaseId: string, data: Record<string, string>) =>
    rg(`/releases/${releaseId}/evidence/ticket`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  attachPR: (releaseId: string, data: Record<string, string>) =>
    rg(`/releases/${releaseId}/evidence/pr`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  attachBuild: (releaseId: string, data: Record<string, string>) =>
    rg(`/releases/${releaseId}/evidence/build`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  checkEvidence: (releaseId: string, workspaceId: string) =>
    rg(`/releases/${releaseId}/evidence/check?workspace_id=${workspaceId}`),

  // Approvals
  getInbox: (approverEmail: string) =>
    rg(`/approvals/inbox?approver_email=${encodeURIComponent(approverEmail)}`),
  approve: (stepId: string, decidedBy: string, note = "") =>
    rg(`/approvals/${stepId}/approve`, {
      method: "POST",
      body: JSON.stringify({ decided_by: decidedBy, note }),
    }),
  reject: (stepId: string, decidedBy: string, note = "") =>
    rg(`/approvals/${stepId}/reject`, {
      method: "POST",
      body: JSON.stringify({ decided_by: decidedBy, note }),
    }),

  // Policies
  listProfiles: () => rg("/policies/profiles"),
  getWorkspaceProfile: (workspaceId: string) =>
    rg(`/policies/profile/${workspaceId}`),
  selectProfile: (workspaceId: string, profile: string) =>
    rg("/policies/profile/select", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, profile }),
    }),

  // Integrations
  listIntegrations: (workspaceId: string) =>
    rg(`/integrations/${workspaceId}`),
  testIntegration: (provider: string, workspaceId: string) =>
    rg(`/integrations/${provider}/test?workspace_id=${workspaceId}`, { method: "POST" }),

  // Dashboard
  getDashboard: (workspaceId: string, days = 30) =>
    rg(`/dashboard/summary/${workspaceId}?days=${days}`),
};
