"use client";

import { useState } from "react";
import { api, DemoScenario, DemoScenarioResult, DemoRunAllResult } from "@/lib/api";

export default function DemoPage() {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [results, setResults] = useState<Record<string, DemoScenarioResult>>({});
  const [allResult, setAllResult] = useState<DemoRunAllResult | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [resetStatus, setResetStatus] = useState<string | null>(null);

  async function loadScenarios() {
    const data = await api.getDemoScenarios();
    setScenarios(data.scenarios);
  }

  async function resetDemo() {
    setLoading("reset");
    const r = await api.resetDemo();
    setResetStatus(`Reset: ${r.objects} objects, ${r.nodes} nodes, ${r.edges} edges`);
    setResults({});
    setAllResult(null);
    await loadScenarios();
    setLoading(null);
  }

  async function runScenario(id: string) {
    setLoading(id);
    const r = await api.runScenario(id);
    setResults((prev) => ({ ...prev, [id]: r }));
    setLoading(null);
  }

  async function runAll() {
    setLoading("all");
    const r = await api.runAllScenarios();
    setAllResult(r);
    for (const res of r.results) {
      setResults((prev) => ({ ...prev, [res.scenario_id]: res }));
    }
    setLoading(null);
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-200">Demo Tenant</h1>
          <p className="text-sm text-slate-500">
            Repeatable demo scenarios for sales and pilot conversations.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={resetDemo}
            disabled={loading !== null}
            className="px-3 py-1.5 text-xs border border-[#1e2330] text-slate-400 rounded hover:text-slate-200 disabled:opacity-50"
          >
            {loading === "reset" ? "Resetting…" : "Reset"}
          </button>
          <button
            onClick={runAll}
            disabled={loading !== null}
            className="px-3 py-1.5 text-xs bg-[#00e5b4] text-[#0d0f14] font-medium rounded hover:bg-[#00c9a0] disabled:opacity-50"
          >
            {loading === "all" ? "Running…" : "Run All"}
          </button>
        </div>
      </div>

      {resetStatus && (
        <div className="p-2 bg-[#00e5b410] border border-[#00e5b430] rounded text-xs text-[#00e5b4]">
          {resetStatus}
        </div>
      )}

      {allResult && (
        <div className="p-3 bg-[#0d0f14] border border-[#1e2330] rounded flex gap-6 text-xs">
          <span className="text-slate-500">
            Total: <span className="text-slate-300">{allResult.total}</span>
          </span>
          <span className="text-green-500">Passed: {allResult.passed}</span>
          <span className="text-red-400">Failed: {allResult.failed}</span>
        </div>
      )}

      {scenarios.length === 0 && (
        <button
          onClick={loadScenarios}
          className="px-4 py-2 bg-[#0d0f14] border border-[#1e2330] rounded text-sm text-slate-400 hover:text-slate-200"
        >
          Load Scenarios
        </button>
      )}

      <div className="grid gap-3">
        {scenarios.map((s) => {
          const result = results[s.scenario_id];
          return (
            <div
              key={s.scenario_id}
              className="p-4 bg-[#0d0f14] border border-[#1e2330] rounded space-y-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-200 font-medium">{s.title}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#1e2330] text-slate-500">
                    {s.expected_outcome}
                  </span>
                  {result && (
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                        result.passed
                          ? "bg-green-900/30 text-green-400"
                          : "bg-red-900/30 text-red-400"
                      }`}
                    >
                      {result.passed ? "PASS" : "FAIL"}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => runScenario(s.scenario_id)}
                  disabled={loading !== null}
                  className="px-2 py-1 text-[10px] border border-[#1e2330] text-slate-500 rounded hover:text-slate-300 disabled:opacity-50"
                >
                  {loading === s.scenario_id ? "…" : "Run"}
                </button>
              </div>
              <p className="text-xs text-slate-500">{s.description}</p>
              <div className="text-[10px] text-slate-600 space-y-0.5">
                {s.steps.map((step, i) => (
                  <div key={i}>
                    {i + 1}. {step}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
