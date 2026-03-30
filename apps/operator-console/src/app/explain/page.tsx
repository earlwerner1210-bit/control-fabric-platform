"use client";

import { useState } from "react";
import { api, BlockExplanation, ReleaseExplanation, CaseExplanation } from "@/lib/api";

type Mode = "block" | "release" | "case";

export default function ExplainPage() {
  const [mode, setMode] = useState<Mode>("block");
  const [inputId, setInputId] = useState("");
  const [loading, setLoading] = useState(false);
  const [blockResult, setBlockResult] = useState<BlockExplanation | null>(null);
  const [releaseResult, setReleaseResult] = useState<ReleaseExplanation | null>(null);
  const [caseResult, setCaseResult] = useState<CaseExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExplain() {
    if (!inputId.trim()) return;
    setLoading(true);
    setError(null);
    setBlockResult(null);
    setReleaseResult(null);
    setCaseResult(null);
    try {
      if (mode === "block") {
        setBlockResult(await api.explainBlock(inputId));
      } else if (mode === "release") {
        setReleaseResult(await api.explainRelease(inputId));
      } else {
        setCaseResult(await api.explainCase(inputId));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-lg font-semibold text-slate-200">Policy Explainability</h1>
      <p className="text-sm text-slate-500">
        Understand why an action was blocked, released, or flagged.
      </p>

      <div className="flex gap-2">
        {(["block", "release", "case"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-3 py-1.5 text-xs rounded border transition-all ${
              mode === m
                ? "bg-[#00e5b415] text-[#00e5b4] border-[#00e5b430]"
                : "text-slate-500 border-[#1e2330] hover:text-slate-300"
            }`}
          >
            Explain {m}
          </button>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          value={inputId}
          onChange={(e) => setInputId(e.target.value)}
          placeholder={`Enter ${mode} ID…`}
          className="flex-1 px-3 py-2 bg-[#0d0f14] border border-[#1e2330] rounded text-sm text-slate-300 placeholder:text-slate-600"
          onKeyDown={(e) => e.key === "Enter" && handleExplain()}
        />
        <button
          onClick={handleExplain}
          disabled={loading}
          className="px-4 py-2 bg-[#00e5b4] text-[#0d0f14] text-sm font-medium rounded hover:bg-[#00c9a0] disabled:opacity-50"
        >
          {loading ? "…" : "Explain"}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-900/20 border border-red-800/30 rounded text-sm text-red-400">
          {error}
        </div>
      )}

      {blockResult && (
        <div className="space-y-4">
          <div className="p-4 bg-[#0d0f14] border border-[#1e2330] rounded space-y-3">
            <div className="text-xs text-red-400 font-medium uppercase tracking-wider">
              Blocked
            </div>
            <p className="text-sm text-slate-300">{blockResult.human_summary}</p>
            <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
              <div>Action: <span className="text-slate-300">{blockResult.action_type}</span></div>
              <div>Gate: <span className="text-red-400">{blockResult.blocking_gate}</span></div>
              <div>Origin: <span className="text-slate-300">{blockResult.origin}</span></div>
              <div>By: <span className="text-slate-300">{blockResult.requested_by}</span></div>
            </div>
          </div>

          {blockResult.gates.length > 0 && (
            <div className="p-4 bg-[#0d0f14] border border-[#1e2330] rounded">
              <div className="text-xs text-slate-500 mb-2 uppercase tracking-wider">
                Gate Timeline
              </div>
              <div className="space-y-1">
                {blockResult.gates.map((g) => (
                  <div key={g.gate_name} className="flex items-center gap-2 text-xs">
                    <span className={g.outcome === "passed" ? "text-green-500" : "text-red-400"}>
                      {g.outcome === "passed" ? "✓" : "✗"}
                    </span>
                    <span className="text-slate-400 w-40">{g.gate_name}</span>
                    <span className="text-slate-600">{g.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {blockResult.remediation_steps.length > 0 && (
            <div className="p-4 bg-[#0d0f14] border border-[#1e2330] rounded">
              <div className="text-xs text-slate-500 mb-2 uppercase tracking-wider">
                Remediation
              </div>
              <ul className="space-y-1">
                {blockResult.remediation_steps.map((s, i) => (
                  <li key={i} className="text-xs text-slate-400">
                    {i + 1}. {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {releaseResult && (
        <div className="p-4 bg-[#0d0f14] border border-[#1e2330] rounded space-y-3">
          <div className="text-xs text-green-500 font-medium uppercase tracking-wider">
            Released
          </div>
          <p className="text-sm text-slate-300">{releaseResult.human_summary}</p>
          <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
            <div>Package: <span className="text-slate-300">{releaseResult.package_id}</span></div>
            <div>Action: <span className="text-slate-300">{releaseResult.action_type}</span></div>
            <div>Hash: <span className="text-slate-300 font-mono">{releaseResult.package_hash}</span></div>
            <div>By: <span className="text-slate-300">{releaseResult.requested_by}</span></div>
          </div>
          <div className="text-xs text-slate-500">
            Gates passed: {releaseResult.gates_passed.join(", ")}
          </div>
        </div>
      )}

      {caseResult && (
        <div className="p-4 bg-[#0d0f14] border border-[#1e2330] rounded space-y-3">
          <div className="text-xs text-amber-400 font-medium uppercase tracking-wider">
            {caseResult.case_type} — {caseResult.severity}
          </div>
          <p className="text-sm text-slate-300">{caseResult.explanation}</p>
          <div className="text-xs text-slate-400">
            <strong className="text-slate-300">What this means:</strong>{" "}
            {caseResult.what_this_means}
          </div>
          <div className="text-xs text-slate-400">
            <strong className="text-slate-300">What to do next:</strong>{" "}
            {caseResult.what_to_do_next}
          </div>
        </div>
      )}
    </div>
  );
}
