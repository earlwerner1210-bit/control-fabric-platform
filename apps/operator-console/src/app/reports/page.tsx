"use client";

import { useState } from "react";
import { api, ReportResult, ReportSummary } from "@/lib/api";

const WINDOWS = ["7d", "30d", "90d"] as const;

export default function ReportsPage() {
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [activeReport, setActiveReport] = useState<ReportResult | null>(null);
  const [window, setWindow] = useState<string>("30d");
  const [loading, setLoading] = useState(false);

  async function loadSummary() {
    setLoading(true);
    try {
      setSummary(await api.getReportSummary());
    } finally {
      setLoading(false);
    }
  }

  async function loadReport(reportId: string) {
    setLoading(true);
    try {
      setActiveReport(await api.getReport(reportId, window));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-lg font-semibold text-slate-200">Reports</h1>
      <p className="text-sm text-slate-500">
        Customer-facing compliance and governance reports.
      </p>

      <div className="flex items-center gap-3">
        <div className="flex gap-1">
          {WINDOWS.map((w) => (
            <button
              key={w}
              onClick={() => setWindow(w)}
              className={`px-2 py-1 text-[10px] rounded border ${
                window === w
                  ? "bg-[#00e5b415] text-[#00e5b4] border-[#00e5b430]"
                  : "text-slate-500 border-[#1e2330] hover:text-slate-300"
              }`}
            >
              {w}
            </button>
          ))}
        </div>
        {!summary && (
          <button
            onClick={loadSummary}
            disabled={loading}
            className="px-3 py-1.5 text-xs bg-[#00e5b4] text-[#0d0f14] font-medium rounded hover:bg-[#00c9a0] disabled:opacity-50"
          >
            {loading ? "Loading…" : "Load Reports"}
          </button>
        )}
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {summary.available_reports.map((r) => (
            <button
              key={r.report_id}
              onClick={() => loadReport(r.report_id)}
              className="p-3 bg-[#0d0f14] border border-[#1e2330] rounded text-left hover:border-[#00e5b430] transition-all"
            >
              <div className="text-xs text-slate-300 font-medium">{r.title}</div>
              <div className="text-[10px] text-slate-600 mt-1">{r.description}</div>
            </button>
          ))}
        </div>
      )}

      {activeReport && (
        <div className="p-4 bg-[#0d0f14] border border-[#1e2330] rounded space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-200 font-medium">{activeReport.title}</div>
            <div className="text-[10px] text-slate-600">
              {activeReport.window} · {activeReport.generated_at}
            </div>
          </div>
          <pre className="text-[10px] text-slate-400 overflow-x-auto">
            {JSON.stringify(activeReport.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
