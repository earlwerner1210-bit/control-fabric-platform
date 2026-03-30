"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { CaseCard } from "@/components/case-card";
import { useState } from "react";

export default function CasesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["cases"],
    queryFn: api.getCases,
    refetchInterval: 15_000,
  });
  const [filter, setFilter] = useState<
    "all" | "critical" | "high" | "medium" | "low"
  >("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const cases = (data?.cases ?? [])
    .filter((c) => filter === "all" || c.severity === filter)
    .filter((c) => typeFilter === "all" || c.case_type === typeFilter)
    .sort((a, b) => b.severity_score - a.severity_score);

  const counts = {
    critical:
      data?.cases.filter((c) => c.severity === "critical").length ?? 0,
    high: data?.cases.filter((c) => c.severity === "high").length ?? 0,
    medium:
      data?.cases.filter((c) => c.severity === "medium").length ?? 0,
    low: data?.cases.filter((c) => c.severity === "low").length ?? 0,
  };

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <h1 className="text-[15px] font-semibold text-slate-200">
          Case Triage Queue
        </h1>
        <p className="text-[12px] text-slate-500 mt-0.5">
          {data?.open_case_count ?? 0} open cases requiring review
        </p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {(["all", "critical", "high", "medium", "low"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`text-[11px] px-3 py-1.5 rounded border transition-colors ${
              filter === s
                ? "bg-[#00e5b415] text-[#00e5b4] border-[#00e5b430]"
                : "text-slate-500 border-[#1e2330] hover:text-slate-300"
            }`}
          >
            {s === "all"
              ? `All (${data?.open_case_count ?? 0})`
              : `${s} (${counts[s]})`}
          </button>
        ))}
        <div className="h-5 w-px bg-[#1e2330]" />
        {(["all", "gap", "conflict", "orphan"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`text-[11px] px-3 py-1.5 rounded border transition-colors ${
              typeFilter === t
                ? "bg-[#ffffff10] text-slate-200 border-[#252d3d]"
                : "text-slate-600 border-[#1e2330] hover:text-slate-400"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 bg-[#111318] border border-[#1e2330] rounded-lg animate-pulse"
            />
          ))}
        </div>
      )}

      <div className="space-y-3">
        {cases.map((c) => (
          <CaseCard key={c.case_id} c={c} />
        ))}
        {!isLoading && cases.length === 0 && (
          <div className="text-center py-12 text-slate-600">
            <div className="text-[14px] mb-1">◈</div>
            <div className="text-[12px]">No cases match this filter</div>
          </div>
        )}
      </div>
    </div>
  );
}
