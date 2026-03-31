"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TENANT = "default";

const FRAMEWORK_COLORS: Record<string, string> = {
  "NIS2 Directive (EU) 2022/2555": "text-blue-400 border-blue-900/40 bg-blue-950/20",
  "Ofcom General Conditions":       "text-emerald-400 border-emerald-900/40 bg-emerald-950/20",
  "SOC2 Type II":                   "text-purple-400 border-purple-900/40 bg-purple-950/20",
  "ISO 27001:2022":                  "text-amber-400 border-amber-900/40 bg-amber-950/20",
};

const STATUS_COLORS: Record<string, { dot: string; label: string; text: string }> = {
  covered:     { dot: "bg-emerald-400", label: "Covered",     text: "text-emerald-400" },
  partial:     { dot: "bg-amber-400",   label: "Partial",     text: "text-amber-400"   },
  not_covered: { dot: "bg-red-500",     label: "Gap",         text: "text-red-400"     },
};

export default function CompliancePage() {
  const [selectedFramework, setSelectedFramework] = useState<string | null>(null);
  const [expandedControl, setExpandedControl] = useState<string | null>(null);

  const { data: report, isLoading } = useQuery({
    queryKey: ["compliance-report", TENANT],
    queryFn: () =>
      fetch(`${API}/compliance/report/${TENANT}?period_days=30`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("cfp_token") || ""}` },
      }).then(r => r.json()),
    refetchInterval: 60000,
  });

  const { data: frameworks } = useQuery({
    queryKey: ["compliance-frameworks"],
    queryFn: () => fetch(`${API}/compliance/coverage`).then(r => r.json()),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[12px] text-slate-500">Generating compliance report...</div>
      </div>
    );
  }

  const r = report as any;
  const coverage: any[] = r?.control_coverage ?? [];
  const fw = selectedFramework
    ? coverage.filter((c: any) => c.framework === selectedFramework)
    : coverage;

  const frameworkNames: string[] = frameworks
    ? frameworks.frameworks?.map((f: any) => f.name)
    : [...new Set(coverage.map((c: any) => c.framework))];

  const coveredCount = coverage.filter((c: any) => c.status === "covered").length;
  const partialCount = coverage.filter((c: any) => c.status === "partial").length;
  const gapCount = coverage.filter((c: any) => c.status === "not_covered").length;
  const totalCount = coverage.length;

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[15px] font-semibold text-slate-200">Compliance Coverage</h1>
          <p className="text-[12px] text-slate-500 mt-0.5">
            NIS2 · Ofcom · SOC2 · ISO 27001 · {totalCount} controls assessed
          </p>
        </div>
        <a
          href={`${API}/compliance/report/${TENANT}/export?format=csv`}
          target="_blank"
          className="text-[11px] px-3 py-1.5 bg-[#111318] border border-[#1e2330] text-slate-400 rounded hover:text-slate-200 transition-colors"
        >
          Export CSV ↓
        </a>
      </div>

      {/* Audit readiness banner */}
      {r && (
        <div className={cn(
          "rounded-lg p-4 border",
          r.audit_readiness_grade === "A"
            ? "bg-[#0a1a12] border-emerald-900/40"
            : r.audit_readiness_grade === "B"
            ? "bg-[#111318] border-[#1e2330]"
            : "bg-[#1a1400] border-yellow-900/40"
        )}>
          <div className="flex items-center gap-4">
            <div className="text-center">
              <div className={cn("text-[36px] font-bold leading-none",
                r.audit_readiness_grade === "A" ? "text-emerald-400"
                : r.audit_readiness_grade === "B" ? "text-[#00e5b4]"
                : "text-amber-400"
              )}>
                {r.audit_readiness_grade}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Audit grade</div>
            </div>
            <div className="flex-1">
              <p className="text-[13px] text-slate-300 font-medium">
                {r.executive_summary?.slice(0, 180)}
                {r.executive_summary?.length > 180 ? "..." : ""}
              </p>
            </div>
            <div className="text-right">
              <div className="text-[24px] font-semibold text-slate-300">{r.audit_readiness_score}</div>
              <div className="text-[10px] text-slate-500">/ 100</div>
            </div>
          </div>
        </div>
      )}

      {/* Coverage summary tiles */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Fully covered", count: coveredCount, color: "text-emerald-400", bg: "bg-emerald-400" },
          { label: "Partial coverage", count: partialCount, color: "text-amber-400", bg: "bg-amber-400" },
          { label: "Coverage gap", count: gapCount, color: "text-red-400", bg: "bg-red-400" },
          { label: "Total controls", count: totalCount, color: "text-slate-300", bg: "bg-slate-500" },
        ].map(({ label, count, color, bg }) => (
          <div key={label} className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 text-center">
            <div className={cn("text-[28px] font-bold", color)}>{count}</div>
            <div className="text-[10px] text-slate-500 mt-1">{label}</div>
            <div className="mt-2 w-full h-1 bg-[#1e2330] rounded-full overflow-hidden">
              <div className={cn("h-full rounded-full", bg)}
                style={{ width: `${Math.round(count / Math.max(totalCount, 1) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>

      {/* Framework filter tabs */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setSelectedFramework(null)}
          className={cn("text-[11px] px-3 py-1.5 rounded border transition-colors",
            !selectedFramework
              ? "bg-[#00e5b415] text-[#00e5b4] border-[#00e5b430]"
              : "text-slate-500 border-[#1e2330] hover:text-slate-300"
          )}>
          All frameworks
        </button>
        {frameworkNames.map((name: string) => (
          <button
            key={name}
            onClick={() => setSelectedFramework(name === selectedFramework ? null : name)}
            className={cn(
              "text-[11px] px-3 py-1.5 rounded border transition-colors",
              selectedFramework === name
                ? "bg-[#00e5b415] text-[#00e5b4] border-[#00e5b430]"
                : "text-slate-500 border-[#1e2330] hover:text-slate-300"
            )}>
            {name.split(" ")[0]}
            {name.includes("NIS2") ? " NIS2" : ""}
          </button>
        ))}
      </div>

      {/* Control coverage list */}
      <div className="bg-[#111318] border border-[#1e2330] rounded-lg overflow-hidden">
        <div className="grid grid-cols-[160px_1fr_90px_80px] gap-3 px-4 py-2.5 border-b border-[#1e2330]
                        text-[10px] text-slate-600 uppercase tracking-wider">
          <span>Framework</span>
          <span>Control</span>
          <span>Article</span>
          <span>Status</span>
        </div>
        {fw.map((ctrl: any) => {
          const statusMeta = STATUS_COLORS[ctrl.status] ?? STATUS_COLORS.not_covered;
          const isExpanded = expandedControl === ctrl.control_id;
          const fwColor = FRAMEWORK_COLORS[ctrl.framework] ?? "text-slate-400";
          return (
            <div key={ctrl.control_id}>
              <div
                className="grid grid-cols-[160px_1fr_90px_80px] gap-3 px-4 py-3
                           border-b border-[#1e2330] items-start cursor-pointer
                           hover:bg-[#ffffff03] transition-colors"
                onClick={() => setExpandedControl(isExpanded ? null : ctrl.control_id)}>
                <div className={cn("text-[10px] font-medium truncate", fwColor)}>
                  {ctrl.framework.split(" ")[0]}
                  {ctrl.framework.includes("NIS2") ? " NIS2" : ""}
                  {ctrl.framework.includes("Ofcom") ? " Ofcom" : ""}
                  {ctrl.framework.includes("SOC2") ? " SOC2" : ""}
                  {ctrl.framework.includes("ISO") ? " ISO 27001" : ""}
                </div>
                <div>
                  <div className="text-[12px] text-slate-300">{ctrl.control}</div>
                  <div className="text-[10px] text-slate-600 font-mono mt-0.5">{ctrl.control_id}</div>
                </div>
                <div className="text-[10px] text-slate-500 font-mono">{ctrl.article}</div>
                <div className="flex items-center gap-1.5">
                  <span className={cn("w-2 h-2 rounded-full flex-shrink-0", statusMeta.dot)} />
                  <span className={cn("text-[10px] font-medium", statusMeta.text)}>
                    {statusMeta.label}
                  </span>
                </div>
              </div>
              {isExpanded && (
                <div className="px-4 py-3 border-b border-[#1e2330] bg-[#0a0c10]">
                  <div className="text-[10px] text-slate-500 mb-1">Evidence</div>
                  <div className="text-[11px] text-slate-400">{ctrl.evidence}</div>
                  {ctrl.covered_by?.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap mt-2">
                      {ctrl.covered_by.map((mod: string) => (
                        <span key={mod}
                          className="text-[9px] px-2 py-0.5 bg-[#00e5b415] text-[#00e5b4] rounded font-mono">
                          {mod}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
