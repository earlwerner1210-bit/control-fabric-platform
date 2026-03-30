"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/utils";

export default function Overview() {
  const qc = useQueryClient();
  const { data: cases } = useQuery({
    queryKey: ["cases"],
    queryFn: api.getCases,
    refetchInterval: 15_000,
  });
  const { data: stats } = useQuery({
    queryKey: ["ingress-stats"],
    queryFn: api.getIngressStats,
  });
  const { data: integrity } = useQuery({
    queryKey: ["integrity"],
    queryFn: api.getAuditIntegrity,
  });
  const { data: exceptions } = useQuery({
    queryKey: ["exceptions"],
    queryFn: api.getActiveExceptions,
  });

  const run = useMutation({
    mutationFn: api.runReconciliation,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cases"] }),
  });

  const critical =
    cases?.cases.filter((c) => c.severity === "critical").length ?? 0;
  const high =
    cases?.cases.filter((c) => c.severity === "high").length ?? 0;
  const total = cases?.open_case_count ?? 0;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[16px] font-semibold text-slate-200 tracking-wide">
            Control Fabric — Operator Console
          </h1>
          <p className="text-[12px] text-slate-500 mt-0.5">
            Platform governance overview
          </p>
        </div>
        <button
          onClick={() => run.mutate()}
          disabled={run.isPending}
          className="text-[12px] px-4 py-2 bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430] rounded hover:bg-[#00e5b425] transition-colors disabled:opacity-50"
        >
          {run.isPending ? "Running..." : "▶ Run Reconciliation"}
        </button>
      </div>

      {/* Stat Grid */}
      <div className="grid grid-cols-4 gap-3">
        {[
          {
            label: "Critical Cases",
            value: critical,
            color: critical > 0 ? "text-red-400" : "text-emerald-400",
            sub: "require immediate action",
          },
          {
            label: "High Cases",
            value: high,
            color: high > 0 ? "text-orange-400" : "text-emerald-400",
            sub: "require review",
          },
          {
            label: "Open Cases",
            value: total,
            color: "text-slate-300",
            sub: "total open",
          },
          {
            label: "Active Exceptions",
            value: exceptions?.count ?? 0,
            color: exceptions?.count
              ? "text-yellow-400"
              : "text-emerald-400",
            sub: "with expiry",
          },
        ].map((s) => (
          <div
            key={s.label}
            className="bg-[#111318] border border-[#1e2330] rounded-lg p-4"
          >
            <div className="text-[10px] text-slate-600 uppercase tracking-wider">
              {s.label}
            </div>
            <div className={`text-[28px] font-semibold mt-1 ${s.color}`}>
              {s.value}
            </div>
            <div className="text-[11px] text-slate-600 mt-0.5">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Platform State */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 space-y-3">
          <div className="text-[11px] text-slate-500 uppercase tracking-wider">
            Platform state
          </div>
          {stats &&
            (
              [
                ["Registry objects", stats.registry_object_count],
                ["Graph nodes", stats.graph_node_count],
                ["Graph edges", stats.graph_edge_count],
                ["Active objects", stats.active_objects],
              ] as const
            ).map(([k, v]) => (
              <div key={k} className="flex justify-between items-center">
                <span className="text-[12px] text-slate-500">{k}</span>
                <span className="text-[13px] font-semibold text-slate-300">
                  {v.toLocaleString()}
                </span>
              </div>
            ))}
        </div>

        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 space-y-3">
          <div className="text-[11px] text-slate-500 uppercase tracking-wider">
            Evidence chain
          </div>
          {integrity && (
            <>
              <div className="flex items-center gap-3">
                <span
                  className={`w-2 h-2 rounded-full ${integrity.chain_valid ? "bg-emerald-400" : "bg-red-400"}`}
                />
                <span className="text-[12px] text-slate-300">
                  {integrity.chain_valid
                    ? "Chain integrity verified"
                    : "Chain integrity FAULT"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[12px] text-slate-500">
                  Total evidence records
                </span>
                <span className="text-[13px] font-semibold text-slate-300">
                  {integrity.total_records.toLocaleString()}
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Recent cases */}
      {cases && cases.cases.length > 0 && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4">
          <div className="text-[11px] text-slate-500 uppercase tracking-wider mb-3">
            Recent cases
          </div>
          <div className="space-y-2">
            {cases.cases.slice(0, 5).map((c) => (
              <div
                key={c.case_id}
                className="flex items-center gap-3 py-1.5 border-b border-[#1e2330] last:border-0"
              >
                <span
                  className={`text-[10px] uppercase font-semibold w-12 flex-shrink-0 ${
                    c.severity === "critical"
                      ? "text-red-400"
                      : c.severity === "high"
                        ? "text-orange-400"
                        : "text-yellow-400"
                  }`}
                >
                  {c.severity}
                </span>
                <span className="text-[12px] text-slate-300 flex-1 truncate">
                  {c.title}
                </span>
                <span className="text-[11px] text-slate-600 flex-shrink-0">
                  {relativeTime(c.detected_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {run.data && (
        <div className="bg-[#0a1a12] border border-emerald-900/40 rounded-lg p-4">
          <div className="text-[11px] text-emerald-400 uppercase tracking-wider mb-2">
            Reconciliation complete
          </div>
          <div className="grid grid-cols-4 gap-4">
            {(
              [
                ["New cases", run.data.new_cases_this_run],
                ["Critical", run.data.by_severity?.critical ?? 0],
                ["High", run.data.by_severity?.high ?? 0],
                ["Total open", run.data.open_cases],
              ] as const
            ).map(([k, v]) => (
              <div key={k}>
                <div className="text-[10px] text-slate-600">{k}</div>
                <div className="text-[16px] font-semibold text-emerald-400">
                  {v}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
