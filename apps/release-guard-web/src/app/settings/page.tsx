"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const WORKSPACE_ID = "demo-workspace";

const PROFILE_DESCRIPTIONS: Record<string, { label: string; description: string; color: string }> = {
  startup_default: {
    label: "Startup",
    description: "Require a Jira ticket and passing CI. One approver for high-risk releases.",
    color: "border-green-200 bg-green-50",
  },
  regulated_default: {
    label: "Regulated",
    description: "Add a security scan. Approvals required for medium risk and above.",
    color: "border-blue-200 bg-blue-50",
  },
  strict: {
    label: "Strict",
    description: "All four checks required. Two approvers for critical releases.",
    color: "border-purple-200 bg-purple-50",
  },
};

export default function SettingsPage() {
  const qc = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const { data: profileData } = useQuery({
    queryKey: ["workspace-profile", WORKSPACE_ID],
    queryFn: () => api.getWorkspaceProfile(WORKSPACE_ID),
  });
  const { data: allProfiles } = useQuery({
    queryKey: ["all-profiles"],
    queryFn: () => api.listProfiles(),
  });
  const { data: integrations } = useQuery({
    queryKey: ["integrations", WORKSPACE_ID],
    queryFn: () => api.listIntegrations(WORKSPACE_ID),
  });

  const selectProfile = useMutation({
    mutationFn: (profile: string) => api.selectProfile(WORKSPACE_ID, profile),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace-profile"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const testIntegration = useMutation({
    mutationFn: (provider: string) => api.testIntegration(provider, WORKSPACE_ID),
  });

  const currentProfile = (profileData as any)?.profile_name;
  const profiles = (allProfiles as any)?.profiles ?? [];
  const ints = (integrations as any)?.integrations ?? [];

  return (
    <div className="max-w-2xl space-y-7">
      <div>
        <h1 className="text-xl font-bold text-slate-800">Settings</h1>
        <p className="text-sm text-slate-500 mt-0.5">Release rules, integrations, and workspace configuration.</p>
      </div>

      {/* Release rules */}
      <section>
        <h2 className="text-sm font-semibold text-slate-700 mb-3">Release rules</h2>
        <p className="text-xs text-slate-400 mb-4">Choose the right level of scrutiny for your team. You can change this at any time.</p>
        <div className="space-y-3">
          {profiles.map((p: any) => {
            const meta = PROFILE_DESCRIPTIONS[p.name] ?? { label: p.name, description: p.description, color: "border-border bg-white" };
            const isSelected = currentProfile === p.name;
            return (
              <button key={p.name}
                onClick={() => selectProfile.mutate(p.name)}
                className={cn(
                  "w-full text-left p-4 rounded-xl border-2 transition-all",
                  isSelected ? "border-brand bg-brand/5" : "border-border bg-white hover:bg-surface-raised"
                )}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-sm text-slate-800">{meta.label}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{meta.description}</p>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {p.required_evidence?.map((e: string) => (
                        <span key={e} className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-500 rounded-md">
                          {e.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                  {isSelected && (
                    <span className="text-xs font-semibold text-brand bg-brand/10 px-2 py-0.5 rounded-md">Active</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
        {saved && <p className="text-xs text-green-600 mt-2">✓ Profile updated</p>}
      </section>

      {/* Integrations */}
      <section>
        <h2 className="text-sm font-semibold text-slate-700 mb-3">Integrations</h2>
        <div className="bg-white rounded-xl border border-border divide-y divide-border">
          {[
            { provider: "github", label: "GitHub", description: "Pull CI results and PR status automatically" },
            { provider: "jira", label: "Jira", description: "Verify tickets exist and are in approved status" },
            { provider: "slack", label: "Slack", description: "Get notified when releases are blocked or approved" },
          ].map(({ provider, label, description }) => {
            const connected = ints.find((i: any) => i.provider === provider);
            return (
              <div key={provider} className="flex items-center gap-4 px-5 py-4">
                <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-sm font-bold text-slate-500 shrink-0">
                  {label[0]}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-700">{label}</p>
                  <p className="text-xs text-slate-400">{description}</p>
                </div>
                <div className="flex items-center gap-2">
                  {connected ? (
                    <>
                      <span className={cn("text-xs font-medium",
                        connected.status === "connected" ? "text-green-600" : "text-red-500")}>
                        {connected.status === "connected" ? "✓ Connected" : "⚠ Error"}
                      </span>
                      <Button variant="ghost" size="sm"
                        onClick={() => testIntegration.mutate(provider)}>
                        Test
                      </Button>
                    </>
                  ) : (
                    <Button variant="secondary" size="sm">Connect</Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
