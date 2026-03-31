"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { cn, timeAgo, STATUS_COLORS, RISK_COLORS } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const WORKSPACE_ID = "demo-workspace";
const STATUSES = ["all", "draft", "pending", "blocked", "approved", "cancelled"];

export default function ReleasesPage() {
  const [statusFilter, setStatusFilter] = useState("all");

  const { data, isLoading } = useQuery({
    queryKey: ["releases", WORKSPACE_ID, statusFilter],
    queryFn: () => api.listReleases(WORKSPACE_ID, statusFilter === "all" ? undefined : statusFilter),
  });

  const releases = (data as any)?.releases ?? [];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800">Releases</h1>
          <p className="text-sm text-slate-500 mt-0.5">{releases.length} releases</p>
        </div>
        <Link href="/releases/new"><Button>+ New release</Button></Link>
      </div>

      {/* Filters */}
      <div className="flex gap-1.5 flex-wrap">
        {STATUSES.map(s => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize",
              statusFilter === s
                ? "bg-brand text-white"
                : "bg-white border border-border text-slate-600 hover:bg-surface-raised"
            )}>
            {s}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-border overflow-hidden">
        {isLoading && (
          <div className="p-8 text-center text-sm text-slate-400">Loading...</div>
        )}
        {!isLoading && releases.length === 0 && (
          <div className="p-12 text-center">
            <p className="text-slate-500 text-sm">No releases yet</p>
            <Link href="/releases/new">
              <Button variant="secondary" size="sm" className="mt-4">Create your first release</Button>
            </Link>
          </div>
        )}
        {releases.map((rel: any, i: number) => (
          <Link key={rel.release_id} href={`/releases/${rel.release_id}`}
            className={cn(
              "flex items-center gap-4 px-5 py-4 hover:bg-surface-raised transition-colors",
              i !== 0 && "border-t border-border"
            )}>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-800 truncate">{rel.title}</p>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="text-xs text-slate-400">{rel.service_name}</span>
                <span className="text-xs text-slate-300">·</span>
                <span className="text-xs text-slate-400">{rel.environment}</span>
                <span className="text-xs text-slate-300">·</span>
                <span className="text-xs text-slate-400">{timeAgo(rel.created_at)}</span>
              </div>
              {rel.status === "blocked" && rel.blocked_reason && (
                <p className="text-xs text-red-600 mt-1">⚠ {rel.blocked_reason}</p>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-slate-400">{rel.evidence_count} checks</span>
              <Badge label={rel.risk_level} className={RISK_COLORS[rel.risk_level]} />
              <Badge label={rel.status} className={STATUS_COLORS[rel.status]} />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
