"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Shell } from "@/components/layout/shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn, timeAgo } from "@/lib/utils";

const WORKSPACE_ID = "demo-workspace";
const APPROVER_EMAIL = "cto@demo.com";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const rg = (path: string, opts?: RequestInit) =>
  fetch(`${API}/rg${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  }).then(r => r.json());

const URGENCY_COLOR: Record<string, string> = {
  critical: "text-red-700 bg-red-50 border-red-200",
  high:     "text-orange-700 bg-orange-50 border-orange-200",
  medium:   "text-amber-700 bg-amber-50 border-amber-200",
  low:      "text-slate-600 bg-slate-50 border-slate-200",
};

const STATUS_COLOR: Record<string, string> = {
  pending_approval: "text-amber-700 bg-amber-50 border-amber-200",
  approved:         "text-green-700 bg-green-50 border-green-200",
  rejected:         "text-red-700 bg-red-50 border-red-200",
};

export default function ExceptionsPage() {
  const qc = useQueryClient();
  const [notes, setNotes] = useState<Record<string, string>>({});

  const { data: pending } = useQuery({
    queryKey: ["exceptions-pending", APPROVER_EMAIL],
    queryFn: () => rg(`/exceptions/pending?approver_email=${encodeURIComponent(APPROVER_EMAIL)}`),
    refetchInterval: 30000,
  });
  const { data: all } = useQuery({
    queryKey: ["exceptions-all", WORKSPACE_ID],
    queryFn: () => rg(`/exceptions?workspace_id=${WORKSPACE_ID}`),
  });

  const approve = useMutation({
    mutationFn: ({ id }: { id: string }) =>
      rg(`/exceptions/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ decided_by: APPROVER_EMAIL, note: notes[id] ?? "" }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exceptions"] }),
  });

  const reject = useMutation({
    mutationFn: ({ id }: { id: string }) =>
      rg(`/exceptions/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ decided_by: APPROVER_EMAIL, note: notes[id] ?? "Rejected" }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exceptions"] }),
  });

  const pendingItems = (pending as any)?.items ?? [];
  const allExceptions = (all as any)?.exceptions ?? [];

  return (
    <Shell>
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-800">Exceptions</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Emergency releases that bypassed normal evidence requirements
          </p>
        </div>

        {pendingItems.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-slate-700 mb-3">
              Needs your decision ({pendingItems.length})
            </h2>
            <div className="space-y-3">
              {pendingItems.map((item: any) => (
                <div key={item.exception_id}
                  className="bg-white rounded-xl border-2 border-red-200 p-5 space-y-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Badge label={item.urgency} className={URGENCY_COLOR[item.urgency]} />
                      <span className="text-xs text-slate-400">{item.age_hours}h ago</span>
                    </div>
                    <p className="font-semibold text-slate-800">{item.release_title}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{item.service_name} · raised by {item.raised_by}</p>
                  </div>
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 space-y-1">
                    <p className="text-xs font-semibold text-red-700">Why they need an exception:</p>
                    <p className="text-sm text-red-800">{item.reason}</p>
                    <p className="text-xs font-semibold text-red-700 mt-2">Business justification:</p>
                    <p className="text-sm text-red-800">{item.business_justification}</p>
                    {item.blocked_reason && (
                      <>
                        <p className="text-xs font-semibold text-slate-600 mt-2">Was blocked because:</p>
                        <p className="text-xs text-slate-600">{item.blocked_reason}</p>
                      </>
                    )}
                  </div>
                  <textarea
                    value={notes[item.exception_id] ?? ""}
                    onChange={e => setNotes(p => ({ ...p, [item.exception_id]: e.target.value }))}
                    placeholder="Add a decision note (required for rejection)"
                    rows={2}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 resize-none" />
                  <div className="flex gap-2">
                    <Button onClick={() => approve.mutate({ id: item.exception_id })}
                      disabled={approve.isPending}>
                      Approve emergency release
                    </Button>
                    <Button variant="danger"
                      onClick={() => reject.mutate({ id: item.exception_id })}
                      disabled={reject.isPending}>
                      Reject
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* History */}
        <div>
          <h2 className="text-sm font-semibold text-slate-700 mb-3">
            Exception history ({allExceptions.length})
          </h2>
          {allExceptions.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
              <p className="text-sm text-slate-400">No exceptions raised yet</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
              {allExceptions.map((e: any) => (
                <div key={e.exception_id} className="flex items-start gap-4 px-5 py-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-700 truncate">{e.reason}</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {e.raised_by} · {timeAgo(e.raised_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge label={e.urgency} className={URGENCY_COLOR[e.urgency] ?? ""} />
                    <Badge label={e.status.replace("_", " ")}
                      className={STATUS_COLOR[e.status] ?? ""} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Shell>
  );
}
