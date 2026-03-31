"use client";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SEVERITY_CONFIG: Record<string, { bg: string; border: string; icon: string }> = {
  error:   { bg: "bg-red-950/30",    border: "border-red-900/40",    icon: "✗" },
  warning: { bg: "bg-amber-950/30",  border: "border-amber-900/40",  icon: "⚠" },
  info:    { bg: "bg-[#111318]",     border: "border-[#1e2330]",     icon: "ℹ" },
};

export default function ReadinessPage() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["readiness"],
    queryFn: () => fetch(`${API}/compliance/readiness`).then(r => r.json()),
    refetchInterval: 60000,
  });

  const r = data as any;
  const checks: any[] = r?.checks ?? [];
  const passing = checks.filter((c: any) => c.passed);
  const failing = checks.filter((c: any) => !c.passed);

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[15px] font-semibold text-slate-200">Production Readiness</h1>
          <p className="text-[12px] text-slate-500 mt-0.5">
            Run before every demo and customer deployment
          </p>
        </div>
        <button onClick={() => refetch()}
          className="text-[11px] px-3 py-1.5 border border-[#1e2330] text-slate-500
                     rounded hover:text-slate-300 transition-colors">
          ↻ Re-check
        </button>
      </div>

      {isLoading && (
        <div className="text-[12px] text-slate-500 text-center py-8">
          Running readiness checks...
        </div>
      )}

      {r && (
        <>
          {/* Overall status */}
          <div className={cn(
            "rounded-lg p-5 border flex items-center gap-5",
            r.passed ? "bg-[#0a1a12] border-emerald-900/40" : "bg-[#1a0a0a] border-red-900/40"
          )}>
            <div className="text-center">
              <div className={cn("text-[40px] font-bold leading-none",
                r.grade === "A" ? "text-emerald-400"
                : r.grade === "B" ? "text-[#00e5b4]"
                : r.grade === "C" ? "text-amber-400"
                : "text-red-400"
              )}>
                {r.grade}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">{r.score}/100</div>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className={cn("text-[13px] font-semibold",
                  r.passed ? "text-emerald-400" : "text-red-400")}>
                  {r.passed ? "✓ Ready to deploy" : "✗ Not ready — fix errors first"}
                </span>
              </div>
              {r.ready_for?.length > 0 && (
                <div className="flex gap-2">
                  {["demo", "pilot", "production"].map(env => (
                    <span key={env}
                      className={cn(
                        "text-[10px] px-2 py-0.5 rounded font-semibold capitalize",
                        r.ready_for.includes(env)
                          ? "bg-emerald-900/40 text-emerald-400"
                          : "bg-[#1e2330] text-slate-600"
                      )}>
                      {r.ready_for.includes(env) ? "✓" : "✗"} {env}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="text-right">
              <div className="text-[11px] text-slate-500">
                {passing.length}/{checks.length} checks passing
              </div>
              <div className="text-[10px] text-slate-600 mt-1">
                {new Date(dataUpdatedAt || Date.now()).toLocaleTimeString()}
              </div>
            </div>
          </div>

          {/* Failing checks first */}
          {failing.length > 0 && (
            <div>
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">
                Needs attention ({failing.length})
              </div>
              <div className="space-y-2">
                {failing.map((check: any) => {
                  const cfg = SEVERITY_CONFIG[check.severity] ?? SEVERITY_CONFIG.info;
                  return (
                    <div key={check.name}
                      className={cn("rounded-lg border p-4", cfg.bg, cfg.border)}>
                      <div className="flex items-start gap-3">
                        <span className={cn("text-[14px] flex-shrink-0",
                          check.severity === "error" ? "text-red-400"
                          : check.severity === "warning" ? "text-amber-400"
                          : "text-slate-400")}>
                          {cfg.icon}
                        </span>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[12px] font-semibold text-slate-300">
                              {check.name}
                            </span>
                            <span className={cn(
                              "text-[9px] px-1.5 py-0.5 rounded font-semibold uppercase",
                              check.severity === "error"
                                ? "bg-red-900/40 text-red-400"
                                : "bg-amber-900/40 text-amber-400"
                            )}>
                              {check.severity}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 mt-1">{check.detail}</p>
                          {check.remediation && (
                            <p className="text-[11px] text-[#00e5b4] mt-1.5">
                              → {check.remediation}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Passing checks */}
          <div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">
              Passing ({passing.length})
            </div>
            <div className="bg-[#111318] border border-[#1e2330] rounded-lg overflow-hidden">
              {passing.map((check: any, i: number) => (
                <div key={check.name}
                  className={cn("flex items-center gap-3 px-4 py-3",
                    i !== 0 && "border-t border-[#1e2330]")}>
                  <span className="text-emerald-400 text-[12px]">✓</span>
                  <div className="flex-1">
                    <span className="text-[12px] text-slate-300">{check.name}</span>
                  </div>
                  <span className="text-[11px] text-slate-500">{check.detail}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
