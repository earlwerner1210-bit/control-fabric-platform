"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function TopBar() {
  const { data: stats } = useQuery({
    queryKey: ["ingress-stats"],
    queryFn: api.getIngressStats,
    refetchInterval: 30_000,
  });
  const { data: integrity } = useQuery({
    queryKey: ["integrity"],
    queryFn: api.getAuditIntegrity,
    refetchInterval: 60_000,
  });

  return (
    <header className="h-10 bg-[#0d0f14] border-b border-[#1e2330] flex items-center px-6 gap-6 flex-shrink-0">
      <div className="flex items-center gap-1.5">
        <span
          className={`w-1.5 h-1.5 rounded-full ${integrity?.chain_valid !== false ? "bg-emerald-400" : "bg-red-400"}`}
        />
        <span className="text-[11px] text-slate-500">
          {integrity?.chain_valid !== false ? "Chain intact" : "Chain fault"}
        </span>
      </div>
      <div className="h-4 w-px bg-[#1e2330]" />
      {stats && (
        <>
          <Stat label="objects" value={stats.registry_object_count} />
          <Stat label="nodes" value={stats.graph_node_count} />
          <Stat label="edges" value={stats.graph_edge_count} />
          <div className="h-4 w-px bg-[#1e2330]" />
          {integrity && (
            <Stat label="evidence records" value={integrity.total_records} />
          )}
        </>
      )}
      <div className="ml-auto text-[11px] text-slate-600">
        {new Date().toISOString().slice(0, 16).replace("T", " ")} UTC
      </div>
    </header>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[13px] font-semibold text-slate-300">
        {value.toLocaleString()}
      </span>
      <span className="text-[11px] text-slate-600">{label}</span>
    </div>
  );
}
