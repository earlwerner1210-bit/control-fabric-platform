"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TENANT = "default";

function Sparkline({ points, color = "#00e5b4" }: {
  points: { value: number }[];
  color?: string;
}) {
  if (!points?.length) return null;
  const values = points.map(p => p.value);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const w = 120;
  const h = 32;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  });
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function TrendBadge({ trend }: { trend: string }) {
  const color = trend === "improving" ? "text-emerald-400"
    : trend === "declining" ? "text-red-400"
    : "text-slate-500";
  const icon = trend === "improving" ? "↑" : trend === "declining" ? "↓" : "→";
  return (
    <span className={cn("text-[10px] font-semibold", color)}>
      {icon} {trend}
    </span>
  );
}

export default function AnalyticsPage() {
  const [period, setPeriod] = useState(30);
  const [granularity, setGranularity] = useState("weekly");

  const { data: trends, isLoading } = useQuery({
    queryKey: ["analytics-trends", TENANT, period, granularity],
    queryFn: () =>
      fetch(`${API}/compliance/analytics/${TENANT}?period_days=${period}&granularity=${granularity}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("cfp_token") || ""}` },
      }).then(r => r.json()),
    refetchInterval: 60000,
  });

  const { data: perf } = useQuery({
    queryKey: ["analytics-perf", TENANT, period],
    queryFn: () =>
      fetch(`${API}/compliance/analytics/${TENANT}/performance?period_days=${period}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("cfp_token") || ""}` },
      }).then(r => r.json()),
  });

  const t = trends as any;
  const p = perf as any;

  const TREND_CARDS = [
    {
      key: "gate_submissions",
      label: "Gate submissions",
      unit: "total",
      color: "#00e5b4",
    },
    {
      key: "block_rate",
      label: "Block rate",
      unit: "%",
      color: "#EF4444",
      improving_when: "down",
    },
    {
      key: "evidence_completeness",
      label: "Evidence completeness",
      unit: "%",
      color: "#22C55E",
      improving_when: "up",
    },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[15px] font-semibold text-slate-200">Analytics</h1>
          <p className="text-[12px] text-slate-500 mt-0.5">Governance performance trends over time</p>
        </div>
        <div className="flex gap-2">
          {[7, 30, 90].map(d => (
            <button key={d} onClick={() => setPeriod(d)}
              className={cn("text-[11px] px-3 py-1.5 rounded border transition-colors",
                period === d
                  ? "bg-[#00e5b415] text-[#00e5b4] border-[#00e5b430]"
                  : "text-slate-500 border-[#1e2330] hover:text-slate-300")}>
              {d}d
            </button>
          ))}
          <div className="w-px bg-[#1e2330] mx-1" />
          {["daily", "weekly"].map(g => (
            <button key={g} onClick={() => setGranularity(g)}
              className={cn("text-[11px] px-3 py-1.5 rounded border transition-colors capitalize",
                granularity === g
                  ? "bg-[#00e5b415] text-[#00e5b4] border-[#00e5b430]"
                  : "text-slate-500 border-[#1e2330] hover:text-slate-300")}>
              {g}
            </button>
          ))}
        </div>
      </div>

      {/* Performance KPIs */}
      {p && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Governance velocity", value: `${p.governance_velocity}/day`, sub: "actions processed" },
            { label: "Block rate", value: `${p.block_rate_pct}%`, sub: "of submissions blocked" },
            { label: "SLM enrichments", value: p.slm_enrichments_used, sub: "domain citations generated" },
            { label: "Webhook events", value: p.webhooks_received, sub: "real-time evidence received" },
          ].map(({ label, value, sub }) => (
            <div key={label} className="bg-[#111318] border border-[#1e2330] rounded-lg p-4">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
              <div className="text-[22px] font-bold text-slate-200 mt-1">{value}</div>
              <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* Trend charts */}
      {isLoading && (
        <div className="text-[12px] text-slate-500 text-center py-8">
          Loading trend data...
        </div>
      )}

      {t && (
        <div className="grid grid-cols-3 gap-4">
          {TREND_CARDS.map(({ key, label, unit, color }) => {
            const trend = t.trends?.[key];
            if (!trend) return null;
            return (
              <div key={key} className="bg-[#111318] border border-[#1e2330] rounded-lg p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
                    <div className="text-[24px] font-bold text-slate-200 mt-0.5">
                      {Math.round(trend.current_value)}{unit === "%" ? "%" : ""}
                    </div>
                  </div>
                  <TrendBadge trend={trend.trend} />
                </div>
                <Sparkline points={trend.points} color={color} />
                <div className="flex justify-between mt-2">
                  {trend.points?.slice(0, 4).map((p: any, i: number) => (
                    <div key={i} className="text-center">
                      <div className="text-[10px] text-slate-300">{Math.round(p.value)}</div>
                      <div className="text-[8px] text-slate-600">{p.period?.split(" ")[0]}</div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Automated insights */}
      {t?.insights?.length > 0 && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-3">
            Automated insights
          </div>
          <div className="space-y-2">
            {t.insights.map((insight: string, i: number) => (
              <div key={i} className="flex items-start gap-2.5">
                <span className="text-[#00e5b4] text-[10px] mt-0.5 flex-shrink-0">◈</span>
                <p className="text-[12px] text-slate-400">{insight}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary table */}
      {t?.summary && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-3">
            Period summary — last {period} days
          </div>
          <div className="grid grid-cols-2 gap-x-12 gap-y-2">
            {Object.entries(t.summary).map(([key, val]) => (
              <div key={key} className="flex justify-between items-center py-1
                                        border-b border-[#1e2330] last:border-0">
                <span className="text-[11px] text-slate-500">
                  {key.replace(/_/g, " ").replace(/pct$/, "%")}
                </span>
                <span className="text-[11px] font-semibold text-slate-300">
                  {String(val)}
                  {key.endsWith("pct") ? "%" : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
