"use client";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  healthy: "text-emerald-400",
  degraded: "text-yellow-400",
  unhealthy: "text-red-400",
  warning: "text-yellow-400",
  unknown: "text-slate-500",
  not_configured: "text-slate-600",
};

const STATUS_DOT: Record<string, string> = {
  healthy: "bg-emerald-400",
  degraded: "bg-yellow-400",
  unhealthy: "bg-red-400",
  warning: "bg-yellow-400",
  unknown: "bg-slate-600",
  not_configured: "bg-slate-700",
};

function StatusDot({ status }: { status: string }) {
  return (
    <span className={cn("inline-block w-2 h-2 rounded-full flex-shrink-0",
      STATUS_DOT[status] ?? "bg-slate-600")} />
  );
}

export default function InfrastructurePage() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["infra-health"],
    queryFn: () => fetch(`${process.env.NEXT_PUBLIC_API_URL}/infra/health`).then(r => r.json()),
    refetchInterval: 30000,
  });

  const updatedTime = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString()
    : "—";

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[15px] font-semibold text-slate-200">Infrastructure Health</h1>
          <p className="text-[12px] text-slate-500 mt-0.5">All platform services — refreshes every 30 seconds</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-slate-600">Updated: {updatedTime}</span>
          <button onClick={() => refetch()}
            className="text-[11px] px-3 py-1.5 border border-[#1e2330] text-slate-500 rounded hover:text-slate-300 transition-colors">
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Overall status banner */}
      {data && (
        <div className={cn("rounded-lg p-4 flex items-center gap-3",
          data.overall === "healthy" ? "bg-[#0a1a12] border border-emerald-900/40"
          : data.overall === "degraded" ? "bg-[#1a1400] border border-yellow-900/40"
          : "bg-[#1a0a0a] border border-red-900/40")}>
          <StatusDot status={data.overall} />
          <span className={cn("text-[13px] font-semibold", STATUS_COLOR[data.overall])}>
            Platform {data.overall.charAt(0).toUpperCase() + data.overall.slice(1)}
          </span>
          <span className="text-[11px] text-slate-500 ml-auto">{data.checked_at?.slice(0, 19).replace("T", " ")} UTC</span>
        </div>
      )}

      {isLoading && (
        <div className="text-[12px] text-slate-500 text-center py-8">Checking services...</div>
      )}

      {/* Service cards */}
      {data?.checks && (
        <div className="space-y-3">
          {Object.entries(data.checks).map(([service, check]: [string, any]) => (
            <div key={service}
              className={cn("bg-[#111318] border rounded-lg p-4 transition-colors",
                check.status === "unhealthy" ? "border-red-900/40"
                : check.status === "degraded" || check.status === "warning" ? "border-yellow-900/40"
                : "border-[#1e2330]")}>
              <div className="flex items-center gap-3 mb-2">
                <StatusDot status={check.status} />
                <span className="text-[13px] font-semibold text-slate-200 capitalize">{service}</span>
                <span className={cn("text-[11px] font-medium ml-auto capitalize", STATUS_COLOR[check.status])}>
                  {check.status?.replace("_", " ")}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 pl-5">
                {Object.entries(check)
                  .filter(([k]) => !["status"].includes(k))
                  .slice(0, 6)
                  .map(([k, v]) => (
                    <div key={k} className="flex gap-2 text-[11px]">
                      <span className="text-slate-600 capitalize">{k.replace(/_/g, " ")}:</span>
                      <span className="text-slate-400">{String(v)}</span>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Quick links */}
      <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4">
        <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-3">Diagnostic endpoints</div>
        <div className="grid grid-cols-2 gap-2">
          {[
            ["/health", "Liveness probe"],
            ["/ready", "Readiness probe"],
            ["/metrics", "Prometheus metrics"],
            ["/infra/health/database", "Database check"],
            ["/infra/health/redis", "Redis check"],
            ["/infra/health/celery", "Celery check"],
          ].map(([path, label]) => (
            <a key={path}
              href={`${process.env.NEXT_PUBLIC_API_URL}${path}`}
              target="_blank"
              className="flex items-center gap-2 text-[11px] text-slate-500 hover:text-slate-300 transition-colors">
              <span className="font-mono text-[#00e5b4]">{path}</span>
              <span className="text-slate-600">— {label}</span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
