"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { cn, timeAgo, STATUS_COLORS, RISK_COLORS } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const WORKSPACE_ID = "demo-workspace";

function KPI({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="bg-white rounded-xl border border-border p-5">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
      <p className={cn("text-3xl font-bold mt-1", color ?? "text-slate-800")}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", WORKSPACE_ID],
    queryFn: () => api.getDashboard(WORKSPACE_ID),
  });

  const { data: releases } = useQuery({
    queryKey: ["releases", WORKSPACE_ID],
    queryFn: () => api.listReleases(WORKSPACE_ID),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400 text-sm">Loading dashboard...</p>
      </div>
    );
  }

  const d = data as any;
  const r = releases as any;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">Last 30 days · {d?.total_releases ?? 0} releases</p>
        </div>
        <Link href="/releases/new">
          <Button>+ New release</Button>
        </Link>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4">
        <KPI label="Approved" value={d?.approved ?? 0} sub="passed all checks" color="text-green-600" />
        <KPI label="Blocked" value={d?.blocked ?? 0} sub="missing evidence or failed" color="text-red-600" />
        <KPI label="Pending approval" value={d?.pending_approvals ?? 0} sub="waiting on approver" color="text-amber-600" />
        <KPI label="Audit readiness" value={d?.audit_readiness_grade ?? "—"} sub={`${d?.approval_rate_pct ?? 0}% approval rate`} />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Recent releases */}
        <div className="col-span-2 bg-white rounded-xl border border-border">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <h2 className="text-sm font-semibold text-slate-700">Recent releases</h2>
            <Link href="/releases" className="text-xs text-brand hover:underline">View all →</Link>
          </div>
          <div className="divide-y divide-border">
            {(r?.releases ?? []).slice(0, 6).map((rel: any) => (
              <Link key={rel.release_id} href={`/releases/${rel.release_id}`}
                className="flex items-center gap-4 px-5 py-3.5 hover:bg-surface-raised transition-colors">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">{rel.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{rel.service_name} · {timeAgo(rel.created_at)}</p>
                </div>
                <Badge label={rel.status} className={STATUS_COLORS[rel.status]} />
                <Badge label={rel.risk_level} className={RISK_COLORS[rel.risk_level]} />
              </Link>
            ))}
            {(!r?.releases || r.releases.length === 0) && (
              <div className="px-5 py-8 text-center">
                <p className="text-sm text-slate-400">No releases yet</p>
                <Link href="/releases/new">
                  <Button variant="secondary" size="sm" className="mt-3">Create your first release</Button>
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Top block reasons */}
        <div className="bg-white rounded-xl border border-border">
          <div className="px-5 py-4 border-b border-border">
            <h2 className="text-sm font-semibold text-slate-700">Why releases get blocked</h2>
          </div>
          <div className="p-5 space-y-3">
            {(d?.top_block_reasons ?? []).map((r: any) => (
              <div key={r.reason}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-600">{r.reason}</span>
                  <span className="font-semibold text-slate-700">{r.count}</span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-red-400 rounded-full"
                    style={{ width: `${Math.min(100, r.count * 20)}%` }} />
                </div>
              </div>
            ))}
            {(!d?.top_block_reasons || d.top_block_reasons.length === 0) && (
              <p className="text-xs text-slate-400">No blocked releases yet — great work!</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
