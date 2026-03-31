"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const SEV_COLOR: Record<string, string> = {
  critical: "text-red-400 bg-red-950/40 border-red-900/60",
  high:     "text-orange-400 bg-orange-950/40 border-orange-900/60",
  medium:   "text-yellow-400 bg-yellow-950/40 border-yellow-900/60",
  low:      "text-slate-400 bg-slate-900/40 border-slate-800",
};

const AGE_COLOR = (hours: number) =>
  hours > 72 ? "text-red-400" : hours > 24 ? "text-orange-400" : "text-slate-500";

function hoursAgo(dateStr: string): number {
  if (!dateStr) return 0;
  return Math.round((Date.now() - new Date(dateStr).getTime()) / 36e5);
}

function slaBreach(sev: string, ageHours: number): boolean {
  const slaMap: Record<string, number> = { critical: 4, high: 24, medium: 72, low: 168 };
  return ageHours > (slaMap[sev] ?? 168);
}

export default function CasesPage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [view, setView] = useState<"queue" | "workload" | "aging">("queue");
  const [sevFilter, setSevFilter] = useState<string>("all");
  const [assignInput, setAssignInput] = useState("");
  const [resolveNote, setResolveNote] = useState("");

  const { data: casesData, isLoading } = useQuery({
    queryKey: ["cases"],
    queryFn: () => fetch(`${process.env.NEXT_PUBLIC_API_URL}/reconciliation/cases`)
      .then(r => r.json()),
    refetchInterval: 30000,
  });
  const { data: workload } = useQuery({
    queryKey: ["case-workload"],
    queryFn: api.getCaseWorkload,
    enabled: view === "workload",
  });
  const { data: aging } = useQuery({
    queryKey: ["case-aging"],
    queryFn: api.getCaseAging,
    enabled: view === "aging",
  });

  const bulkAssign = useMutation({
    mutationFn: () => api.bulkAssign([...selected], assignInput),
    onSuccess: () => { setSelected(new Set()); setAssignInput(""); qc.invalidateQueries({ queryKey: ["cases"] }); },
  });
  const bulkResolve = useMutation({
    mutationFn: () => api.bulkResolve([...selected], resolveNote || "Bulk resolved"),
    onSuccess: () => { setSelected(new Set()); setResolveNote(""); qc.invalidateQueries({ queryKey: ["cases"] }); },
  });
  const bulkSuppress = useMutation({
    mutationFn: () => api.bulkSuppress([...selected]),
    onSuccess: () => { setSelected(new Set()); qc.invalidateQueries({ queryKey: ["cases"] }); },
  });

  const cases: any[] = casesData?.cases ?? [];
  const filtered = sevFilter === "all" ? cases : cases.filter((c: any) => c.severity === sevFilter);
  const allSelected = filtered.length > 0 && filtered.every((c: any) => selected.has(c.case_id));

  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(filtered.map((c: any) => c.case_id)));
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[15px] font-semibold text-slate-200">Case Queue</h1>
          <p className="text-[12px] text-slate-500 mt-0.5">
            {casesData?.open_case_count ?? 0} open ·{" "}
            {cases.filter((c: any) => slaBreach(c.severity, hoursAgo(c.detected_at))).length} SLA breached
          </p>
        </div>
        <div className="flex gap-2">
          {(["queue", "workload", "aging"] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              className={cn("text-[11px] px-3 py-1.5 rounded border transition-colors capitalize",
                view === v ? "bg-[#00e5b415] text-[#00e5b4] border-[#00e5b430]"
                           : "text-slate-500 border-[#1e2330] hover:text-slate-300")}>
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="bg-[#111318] border border-[#00e5b430] rounded-lg p-3 flex items-center gap-3">
          <span className="text-[12px] text-[#00e5b4]">{selected.size} selected</span>
          <div className="flex gap-2 ml-auto">
            <input value={assignInput} onChange={e => setAssignInput(e.target.value)}
              placeholder="Assign to email..."
              className="text-[11px] bg-[#0a0c10] border border-[#252d3d] rounded px-2 py-1.5 text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4] w-48" />
            <button onClick={() => bulkAssign.mutate()} disabled={!assignInput || bulkAssign.isPending}
              className="text-[11px] px-3 py-1.5 bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430] rounded disabled:opacity-40">
              Assign
            </button>
            <input value={resolveNote} onChange={e => setResolveNote(e.target.value)}
              placeholder="Resolution note..."
              className="text-[11px] bg-[#0a0c10] border border-[#252d3d] rounded px-2 py-1.5 text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4] w-48" />
            <button onClick={() => bulkResolve.mutate()} disabled={bulkResolve.isPending}
              className="text-[11px] px-3 py-1.5 bg-emerald-900/40 text-emerald-400 border border-emerald-900/60 rounded disabled:opacity-40">
              Resolve
            </button>
            <button onClick={() => bulkSuppress.mutate()} disabled={bulkSuppress.isPending}
              className="text-[11px] px-3 py-1.5 text-slate-500 border border-[#1e2330] rounded hover:text-slate-300 disabled:opacity-40">
              Suppress
            </button>
          </div>
        </div>
      )}

      {/* QUEUE VIEW */}
      {view === "queue" && (
        <>
          {/* Filters */}
          <div className="flex gap-2">
            {["all", "critical", "high", "medium", "low"].map(s => (
              <button key={s} onClick={() => setSevFilter(s)}
                className={cn("text-[11px] px-3 py-1.5 rounded border transition-colors capitalize",
                  sevFilter === s ? "bg-[#00e5b415] text-[#00e5b4] border-[#00e5b430]"
                                  : "text-slate-500 border-[#1e2330] hover:text-slate-300")}>
                {s}
              </button>
            ))}
          </div>

          {isLoading && <div className="text-[12px] text-slate-500 text-center py-8">Loading cases...</div>}

          {!isLoading && filtered.length === 0 && (
            <div className="text-[12px] text-slate-500 text-center py-12">
              No {sevFilter !== "all" ? sevFilter : ""} cases open
            </div>
          )}

          {/* Case table */}
          {filtered.length > 0 && (
            <div className="bg-[#111318] border border-[#1e2330] rounded-lg overflow-hidden">
              {/* Table header */}
              <div className="grid grid-cols-[24px_1fr_100px_80px_80px_120px] gap-3 px-4 py-2.5 border-b border-[#1e2330] text-[10px] text-slate-600 uppercase tracking-wider">
                <input type="checkbox" checked={allSelected} onChange={toggleAll}
                  className="w-3 h-3 accent-[#00e5b4] mt-0.5" />
                <span>Case</span>
                <span>Severity</span>
                <span>Age</span>
                <span>SLA</span>
                <span>Actions</span>
              </div>

              {/* Cases */}
              {filtered.map((c: any) => {
                const ageH = hoursAgo(c.detected_at);
                const breach = slaBreach(c.severity, ageH);
                const isSelected = selected.has(c.case_id);
                return (
                  <div key={c.case_id}
                    className={cn("grid grid-cols-[24px_1fr_100px_80px_80px_120px] gap-3 px-4 py-3 border-b border-[#1e2330] last:border-0 items-start transition-colors",
                      isSelected ? "bg-[#00e5b408]" : "hover:bg-[#ffffff03]")}>
                    <input type="checkbox" checked={isSelected}
                      onChange={() => {
                        const next = new Set(selected);
                        if (isSelected) next.delete(c.case_id);
                        else next.add(c.case_id);
                        setSelected(next);
                      }}
                      className="w-3 h-3 accent-[#00e5b4] mt-1" />

                    <div>
                      <div className="text-[12px] font-medium text-slate-300 leading-tight">{c.title}</div>
                      <div className="text-[10px] text-slate-600 mt-0.5 font-mono">{c.case_id?.slice(0, 12)}...</div>
                      {c.affected_planes?.length > 0 && (
                        <div className="flex gap-1 mt-1 flex-wrap">
                          {c.affected_planes.map((p: string) => (
                            <span key={p} className="text-[9px] px-1.5 py-0.5 bg-[#1e2330] text-slate-500 rounded">{p}</span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div>
                      <span className={cn("text-[10px] px-2 py-1 rounded border font-semibold uppercase", SEV_COLOR[c.severity] ?? "text-slate-500")}>
                        {c.severity}
                      </span>
                    </div>

                    <div className={cn("text-[11px] font-mono", AGE_COLOR(ageH))}>
                      {ageH < 1 ? "<1h" : ageH < 24 ? `${ageH}h` : `${Math.floor(ageH/24)}d`}
                    </div>

                    <div>
                      {breach ? (
                        <span className="text-[10px] text-red-400 font-semibold">BREACH</span>
                      ) : (
                        <span className="text-[10px] text-emerald-400">Within SLA</span>
                      )}
                    </div>

                    <div className="flex gap-1.5">
                      <button
                        onClick={() => { setSelected(new Set([c.case_id])); }}
                        className="text-[10px] px-2 py-1 text-slate-500 border border-[#1e2330] rounded hover:text-slate-300 transition-colors">
                        Select
                      </button>
                      <a href={`/explain?mode=case&id=${c.case_id}`}
                        className="text-[10px] px-2 py-1 text-[#00e5b4] border border-[#00e5b430] rounded hover:bg-[#00e5b415] transition-colors">
                        Explain
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* WORKLOAD VIEW */}
      {view === "workload" && workload && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5 space-y-4">
          <div className="flex gap-6 text-center">
            <div><div className="text-[24px] font-semibold text-slate-300">{workload.total_open}</div><div className="text-[10px] text-slate-600">Total open</div></div>
            <div><div className="text-[24px] font-semibold text-orange-400">{workload.total_unassigned}</div><div className="text-[10px] text-slate-600">Unassigned</div></div>
            <div><div className="text-[24px] font-semibold text-[#00e5b4]">{workload.assignees}</div><div className="text-[10px] text-slate-600">Assignees</div></div>
          </div>
          {Object.entries(workload.workload ?? {}).map(([assignee, data]: [string, any]) => (
            <div key={assignee} className="border border-[#1e2330] rounded-lg p-3">
              <div className="flex justify-between items-center mb-2">
                <span className="text-[12px] font-medium text-slate-300">{assignee}</span>
                <span className="text-[11px] text-slate-500">{data.count} cases</span>
              </div>
              <div className="w-full bg-[#1e2330] rounded-full h-1.5">
                <div className="bg-[#00e5b4] h-1.5 rounded-full"
                  style={{ width: `${Math.min(100, (data.count / Math.max(workload.total_open, 1)) * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* AGING / SLA VIEW */}
      {view === "aging" && aging && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5 space-y-5">
          <div className="grid grid-cols-4 gap-4 text-center">
            {Object.entries(aging.buckets ?? {}).map(([bucket, count]) => (
              <div key={bucket}>
                <div className="text-[20px] font-semibold text-slate-300">{String(count)}</div>
                <div className="text-[10px] text-slate-600">{bucket.replace(/_/g, " ")}</div>
              </div>
            ))}
          </div>
          {aging.sla_breached > 0 && (
            <div>
              <div className="text-[11px] text-red-400 uppercase tracking-wider mb-2">SLA breaches — {aging.sla_breached} cases</div>
              {(aging.sla_breaches ?? []).slice(0, 10).map((b: any) => (
                <div key={b.case_id} className="flex items-center gap-3 py-2 border-b border-[#1e2330] last:border-0 text-[11px]">
                  <span className={cn("px-2 py-0.5 rounded border text-[10px] font-semibold uppercase", SEV_COLOR[b.severity])}>{b.severity}</span>
                  <span className="font-mono text-slate-400">{b.case_id?.slice(0, 12)}...</span>
                  <span className="text-red-400 ml-auto">+{b.breached_by_hours}h over SLA</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
