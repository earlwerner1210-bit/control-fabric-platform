"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function RulesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["rules"],
    queryFn: api.getRules,
  });

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <h1 className="text-[15px] font-semibold text-slate-200">
          Reconciliation Rules
        </h1>
        <p className="text-[12px] text-slate-500 mt-0.5">
          {data?.rule_count ?? 0} active rules across all domain packs
        </p>
      </div>

      {isLoading && (
        <div className="text-[12px] text-slate-500 text-center py-8">
          Loading rules...
        </div>
      )}

      <div className="space-y-2">
        {data?.rules.map((r) => (
          <div
            key={r.rule_id}
            className="bg-[#111318] border border-[#1e2330] rounded-lg p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-[#00e5b4]">
                    {r.rule_id}
                  </span>
                  <span className="text-[10px] text-slate-600">·</span>
                  <span className="text-[10px] text-slate-600">
                    {r.domain_pack}
                  </span>
                  <span
                    className={`ml-1 text-[10px] px-1.5 py-0.5 rounded ${r.enabled ? "text-emerald-400 bg-emerald-950/40" : "text-slate-600 bg-[#1e2330]"}`}
                  >
                    {r.enabled ? "enabled" : "disabled"}
                  </span>
                </div>
                <div className="text-[13px] text-slate-200 mt-1">
                  {r.rule_name.replace(/_/g, " ")}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {r.description}
                </div>
              </div>
              <span
                className={`text-[10px] font-semibold uppercase flex-shrink-0 ${
                  r.severity === "critical"
                    ? "text-red-400"
                    : r.severity === "high"
                      ? "text-orange-400"
                      : "text-yellow-400"
                }`}
              >
                {r.severity}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-3 text-[11px] font-mono">
              <span className="text-slate-500">{r.source_plane}</span>
              <span className="text-slate-600">
                —[{r.required_relationship}]→
              </span>
              <span className="text-slate-500">{r.target_plane}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
