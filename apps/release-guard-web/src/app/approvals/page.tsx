"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn, RISK_COLORS } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const APPROVER_EMAIL = "approver@company.com";

export default function ApprovalsPage() {
  const qc = useQueryClient();
  const [decisions, setDecisions] = useState<Record<string, { note: string }>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["approvals-inbox", APPROVER_EMAIL],
    queryFn: () => api.getInbox(APPROVER_EMAIL),
    refetchInterval: 30000,
  });

  const approve = useMutation({
    mutationFn: ({ stepId }: { stepId: string }) =>
      api.approve(stepId, APPROVER_EMAIL, decisions[stepId]?.note ?? ""),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approvals-inbox"] }),
  });

  const reject = useMutation({
    mutationFn: ({ stepId }: { stepId: string }) =>
      api.reject(stepId, APPROVER_EMAIL, decisions[stepId]?.note ?? "Rejected by approver"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approvals-inbox"] }),
  });

  const items = (data as any)?.items ?? [];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-800">Approvals inbox</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {items.length} pending · Releases waiting for your review
        </p>
      </div>

      {isLoading && <div className="text-sm text-slate-400 text-center py-8">Loading...</div>}

      {!isLoading && items.length === 0 && (
        <div className="bg-white rounded-xl border border-border p-12 text-center">
          <p className="text-2xl mb-2">✓</p>
          <p className="text-sm font-semibold text-slate-700">All caught up</p>
          <p className="text-xs text-slate-400 mt-1">No releases waiting for your approval</p>
        </div>
      )}

      <div className="space-y-3">
        {items.map((item: any) => (
          <div key={item.step_id}
            className={cn(
              "bg-white rounded-xl border p-5 space-y-4",
              item.sla_breached ? "border-red-200" : "border-border"
            )}>
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Badge label={item.risk_level} className={RISK_COLORS[item.risk_level]} />
                  {item.sla_breached && (
                    <span className="text-xs font-semibold text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded-md">
                      ⚠ SLA overdue
                    </span>
                  )}
                </div>
                <p className="font-semibold text-slate-800">{item.release_title}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {item.service_name} · {item.environment} · submitted by {item.submitted_by} · {item.age_hours}h ago
                </p>
              </div>
            </div>

            {/* Note */}
            <textarea
              value={decisions[item.step_id]?.note ?? ""}
              onChange={e => setDecisions(p => ({ ...p, [item.step_id]: { note: e.target.value } }))}
              placeholder="Add a note (optional for approval, recommended for rejection)"
              rows={2}
              className="w-full border border-border rounded-lg px-3 py-2 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/30 resize-none" />

            {/* Actions */}
            <div className="flex gap-2">
              <Button onClick={() => approve.mutate({ stepId: item.step_id })}
                disabled={approve.isPending}>
                ✓ Approve release
              </Button>
              <Button variant="danger" onClick={() => reject.mutate({ stepId: item.step_id })}
                disabled={reject.isPending}>
                ✗ Reject
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
