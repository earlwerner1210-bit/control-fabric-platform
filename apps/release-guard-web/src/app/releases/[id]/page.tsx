/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Shell } from "@/components/layout/shell";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, STATUS_COLORS, RISK_COLORS, timeAgo } from "@/lib/utils";

const WORKSPACE_ID = "demo-workspace";
const EVIDENCE_TYPES = [
  { key: "ticket", label: "Jira ticket", fn: "attachTicket", placeholder: "CR-1234" },
  { key: "pr", label: "GitHub PR", fn: "attachPR", placeholder: "PR #123 or URL" },
  { key: "build", label: "CI/CD result", fn: "attachBuild", placeholder: "Build ID or URL" },
];

export default function ReleaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [addingEvidence, setAddingEvidence] = useState<string | null>(null);
  const [evidenceForm, setEvidenceForm] = useState({ title: "", reference: "", url: "" });

  const { data: release, isLoading } = useQuery({
    queryKey: ["release", id],
    queryFn: () => api.getRelease(id),
    refetchInterval: 10000,
  });
  const { data: evidence } = useQuery({
    queryKey: ["evidence", id],
    queryFn: () => api.checkEvidence(id, WORKSPACE_ID),
  });
  const { data: explain } = useQuery({
    queryKey: ["explain", id],
    queryFn: () => api.explainRelease(id),
    enabled: !!(release as any)?.status && ["blocked", "approved"].includes((release as any).status),
  });
  const { data: timeline } = useQuery({
    queryKey: ["timeline", id],
    queryFn: () => api.getReleaseTimeline(id),
  });

  const submit = useMutation({
    mutationFn: () => api.submitRelease(id, WORKSPACE_ID),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["release", id] }),
  });

  const addEvidence = useMutation({
    mutationFn: ({ type }: { type: string }) => {
      const fn = EVIDENCE_TYPES.find(e => e.key === type)?.fn as keyof typeof api;
      return (api[fn] as Function)(id, { ...evidenceForm, workspace_id: WORKSPACE_ID, added_by: "you@company.com" });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["evidence", id] });
      qc.invalidateQueries({ queryKey: ["release", id] });
      setAddingEvidence(null);
      setEvidenceForm({ title: "", reference: "", url: "" });
    },
  });

  if (isLoading) return <Shell><div className="text-sm text-slate-400 py-8 text-center">Loading...</div></Shell>;

  const rel = release as any;
  const ev = evidence as any;
  const exp = explain as any;
  const tl = (timeline as any)?.timeline ?? [];

  return (
    <Shell>
      <div className="max-w-3xl space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge label={rel?.status} className={STATUS_COLORS[rel?.status]} />
              <Badge label={rel?.risk_level} className={RISK_COLORS[rel?.risk_level]} />
            </div>
            <h1 className="text-xl font-bold text-slate-800">{rel?.title}</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              {rel?.service_name} · {rel?.environment} · {timeAgo(rel?.created_at)}
            </p>
          </div>
          {["draft", "blocked"].includes(rel?.status) && (
            <Button onClick={() => submit.mutate()} disabled={submit.isPending}>
              {submit.isPending ? "Submitting..." : "Submit for approval →"}
            </Button>
          )}
        </div>

        {/* Explanation panel */}
        {exp && (
          <div className={cn(
            "rounded-xl p-5 border",
            exp.outcome === "approved"
              ? "bg-green-50 border-green-200"
              : exp.outcome === "blocked"
              ? "bg-red-50 border-red-200"
              : "bg-amber-50 border-amber-200"
          )}>
            <p className={cn("font-semibold text-sm",
              exp.outcome === "approved" ? "text-green-800" : "text-red-800")}>
              {exp.title}
            </p>
            <p className="text-sm mt-1 text-slate-700">{exp.reason}</p>
            {exp.what_to_do?.length > 0 && (
              <ul className="mt-3 space-y-1">
                {exp.what_to_do.map((step: string, i: number) => (
                  <li key={i} className="text-sm text-red-700 flex items-center gap-2">
                    <span className="text-red-400">→</span> {step}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Evidence checklist */}
        <div className="bg-white rounded-xl border border-border">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <div>
              <h2 className="text-sm font-semibold text-slate-700">Evidence checklist</h2>
              {ev && (
                <p className="text-xs text-slate-400 mt-0.5">
                  {ev.complete_count} of {ev.total_required} checks complete
                </p>
              )}
            </div>
          </div>
          <div className="divide-y divide-border">
            {ev?.checks?.map((check: any) => (
              <div key={check.evidence_type} className="flex items-center gap-4 px-5 py-3.5">
                <div className={cn(
                  "w-5 h-5 rounded-full flex items-center justify-center text-xs shrink-0",
                  check.complete ? "bg-green-100 text-green-600" : "bg-slate-100 text-slate-400"
                )}>
                  {check.complete ? "✓" : "○"}
                </div>
                <div className="flex-1">
                  <p className={cn("text-sm font-medium", check.complete ? "text-slate-700" : "text-slate-500")}>
                    {check.check}
                  </p>
                  {!check.complete && (
                    <p className="text-xs text-slate-400">Required — not yet attached</p>
                  )}
                </div>
                {!check.complete && rel?.status !== "approved" && (
                  <Button variant="secondary" size="sm"
                    onClick={() => setAddingEvidence(check.evidence_type)}>
                    + Add
                  </Button>
                )}
              </div>
            ))}
          </div>

          {/* Add evidence form */}
          {addingEvidence && (
            <div className="border-t border-border px-5 py-4 bg-surface-raised">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">
                Add {addingEvidence.replace(/_/g, " ")}
              </p>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <input value={evidenceForm.title}
                  onChange={e => setEvidenceForm(p => ({ ...p, title: e.target.value }))}
                  placeholder="Label or title"
                  className="border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
                <input value={evidenceForm.reference}
                  onChange={e => setEvidenceForm(p => ({ ...p, reference: e.target.value }))}
                  placeholder="Reference (ticket ID, build ID, PR #)"
                  className="border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
              </div>
              <div className="flex gap-2">
                <Button size="sm"
                  disabled={!evidenceForm.title || !evidenceForm.reference || addEvidence.isPending}
                  onClick={() => {
                    const type = EVIDENCE_TYPES.find(e =>
                      e.key === addingEvidence ||
                      addingEvidence.includes(e.key)
                    )?.key ?? "ticket";
                    addEvidence.mutate({ type });
                  }}>
                  Attach
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setAddingEvidence(null)}>Cancel</Button>
              </div>
            </div>
          )}
        </div>

        {/* Audit timeline */}
        {tl.length > 0 && (
          <div className="bg-white rounded-xl border border-border">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-slate-700">Activity timeline</h2>
            </div>
            <div className="px-5 py-4 space-y-3">
              {tl.map((entry: any, i: number) => (
                <div key={i} className="flex gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-brand mt-2 shrink-0" />
                  <div>
                    <p className="text-sm text-slate-700">{entry.detail}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{entry.by} · {timeAgo(entry.at)}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
