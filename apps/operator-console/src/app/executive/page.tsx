"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const RISK_COLOR: Record<string, string> = {
  healthy: "text-emerald-400",
  at_risk: "text-yellow-400",
  churn_risk: "text-red-400",
};

const GRADE_COLOR: Record<string, string> = {
  A: "text-emerald-400", B: "text-emerald-300",
  C: "text-yellow-400",  D: "text-orange-400", F: "text-red-400",
};

export default function ExecutivePage() {
  const { data: summary } = useQuery({ queryKey: ["report-summary"], queryFn: api.getReportSummary });
  const { data: blocked } = useQuery({ queryKey: ["report-blocked"], queryFn: () => api.getReport("blocked-unsafe-actions", "30d") as Promise<any> });
  const { data: evidence } = useQuery({ queryKey: ["report-evidence"], queryFn: () => api.getReport("evidence-completeness", "30d") as Promise<any> });
  const { data: readiness } = useQuery({ queryKey: ["report-readiness"], queryFn: () => api.getReport("audit-readiness", "30d") as Promise<any> });
  const { data: overview } = useQuery({ queryKey: ["metering-overview"], queryFn: () => fetch(`${process.env.NEXT_PUBLIC_API_URL}/metering/overview`).then(r => r.json()) });

  const auditGrade = readiness?.summary?.grade ?? "—";
  const auditScore = readiness?.summary?.score ?? 0;
  const passRate = (summary as any)?.pass_rate_pct ?? 0;
  const blockedCount = (summary as any)?.blocked_count ?? 0;
  const completeness = evidence?.summary?.completeness_pct ?? 0;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-[15px] font-semibold text-slate-200">Executive Dashboard</h1>
        <p className="text-[12px] text-slate-500 mt-0.5">Governance posture for board and compliance reporting</p>
      </div>

      {/* KPI tiles */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Audit readiness", value: auditGrade, sub: `${auditScore}/100`, color: GRADE_COLOR[auditGrade] ?? "text-slate-300" },
          { label: "Gate pass rate (30d)", value: `${passRate}%`, sub: "evidenced releases", color: passRate >= 90 ? "text-emerald-400" : passRate >= 75 ? "text-yellow-400" : "text-red-400" },
          { label: "Unsafe actions blocked", value: blockedCount, sub: "last 30 days", color: "text-[#00e5b4]" },
          { label: "Evidence completeness", value: `${completeness}%`, sub: "of actions governed", color: completeness >= 90 ? "text-emerald-400" : completeness >= 70 ? "text-yellow-400" : "text-red-400" },
        ].map(({ label, value, sub, color }) => (
          <div key={label} className="bg-[#111318] border border-[#1e2330] rounded-lg p-5">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
            <div className={cn("text-[36px] font-semibold mt-1 leading-none", color)}>{value}</div>
            <div className="text-[11px] text-slate-600 mt-1">{sub}</div>
          </div>
        ))}
      </div>

      {/* Audit readiness breakdown */}
      {readiness?.components && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5">
          <div className="text-[11px] text-slate-500 uppercase tracking-wider mb-4">Audit readiness — component breakdown</div>
          <div className="space-y-3">
            {readiness.components.map((c: any) => (
              <div key={c.name} className="flex items-center gap-4">
                <div className="w-48 text-[12px] text-slate-400">{c.name}</div>
                <div className="flex-1 h-1.5 bg-[#1e2330] rounded-full overflow-hidden">
                  <div className={cn("h-full rounded-full", c.passed ? "bg-emerald-400" : "bg-[#333]")}
                    style={{ width: `${c.passed ? 100 : 0}%` }} />
                </div>
                <div className={cn("text-[11px] w-16 text-right", c.passed ? "text-emerald-400" : "text-slate-600")}>
                  {c.passed ? `+${c.points}` : "—"}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Platform telemetry */}
      {overview && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5">
          <div className="text-[11px] text-slate-500 uppercase tracking-wider mb-4">Platform activity</div>
          <div className="grid grid-cols-5 gap-3">
            {Object.entries(overview.event_breakdown || {}).slice(0, 5).map(([key, val]) => (
              <div key={key} className="text-center">
                <div className="text-[20px] font-semibold text-slate-300">{String(val)}</div>
                <div className="text-[10px] text-slate-600 mt-0.5">{key.replace(/_/g, " ")}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Insight panel */}
      {readiness?.insight && (
        <div className="bg-[#0a1a12] border border-emerald-900/40 rounded-lg p-4">
          <div className="text-[10px] text-emerald-400 uppercase tracking-wider mb-1">Governance insight</div>
          <div className="text-[13px] text-slate-300">{readiness.insight}</div>
        </div>
      )}

      {/* Export for board */}
      <div className="flex gap-3">
        {[
          { label: "Export audit manifest", href: `/api/audit/export/manifest` },
          { label: "Export full audit trail (JSON)", href: `/api/audit/export/json` },
          { label: "Export audit trail (CSV)", href: `/api/audit/export/csv` },
        ].map(({ label, href }) => (
          <a key={label} href={`${process.env.NEXT_PUBLIC_API_URL}${href}`} target="_blank"
            className="text-[11px] px-4 py-2 bg-[#111318] text-slate-400 border border-[#1e2330] rounded hover:text-slate-200 transition-colors">
            {label}
          </a>
        ))}
      </div>
    </div>
  );
}
