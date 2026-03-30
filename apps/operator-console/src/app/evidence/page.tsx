"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { shortHash, shortDate } from "@/lib/utils";

export default function EvidencePage() {
  const [sessionId, setSessionId] = useState("");
  const [queried, setQueried] = useState("");
  const { data: integrity } = useQuery({
    queryKey: ["integrity"],
    queryFn: api.getAuditIntegrity,
  });
  const { data: audit, isLoading } = useQuery({
    queryKey: ["audit", queried],
    queryFn: () => api.getSessionAudit(queried),
    enabled: queried.length > 8,
  });

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <h1 className="text-[15px] font-semibold text-slate-200">
          Evidence Chain Inspector
        </h1>
        <p className="text-[12px] text-slate-500 mt-0.5">
          Inspect cryptographic evidence records for any session
        </p>
      </div>

      {integrity && (
        <div
          className={`border rounded-lg p-4 flex items-center gap-3 ${integrity.chain_valid ? "bg-[#0a1a12] border-emerald-900/40" : "bg-[#1a0a0a] border-red-900/40"}`}
        >
          <span
            className={`w-2 h-2 rounded-full flex-shrink-0 ${integrity.chain_valid ? "bg-emerald-400" : "bg-red-400"}`}
          />
          <div>
            <div
              className={`text-[12px] font-semibold ${integrity.chain_valid ? "text-emerald-400" : "text-red-400"}`}
            >
              {integrity.chain_valid
                ? "Platform-wide evidence chain intact"
                : "Evidence chain integrity fault detected"}
            </div>
            <div className="text-[11px] text-slate-500">
              {integrity.total_records.toLocaleString()} total records ·
              all-origin coverage
            </div>
          </div>
        </div>
      )}

      <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4">
        <div className="text-[11px] text-slate-500 uppercase tracking-wider mb-3">
          Session lookup
        </div>
        <div className="flex gap-2">
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="Paste session ID..."
            className="flex-1 bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4]"
          />
          <button
            onClick={() => setQueried(sessionId)}
            className="px-4 py-2 text-[12px] bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430] rounded hover:bg-[#00e5b425] transition-colors"
          >
            Inspect
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="text-[12px] text-slate-500 text-center py-8">
          Loading evidence records...
        </div>
      )}

      {audit && (
        <div className="space-y-3">
          <div className="text-[11px] text-slate-500">
            {audit.record_count} evidence records for session{" "}
            {shortHash(queried)}
          </div>
          {audit.records.map((r) => (
            <div
              key={r.record_id}
              className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span
                  className={`text-[11px] uppercase font-semibold px-2 py-0.5 rounded border ${
                    r.final_status === "complete"
                      ? "text-emerald-400 border-emerald-900/60 bg-emerald-950/40"
                      : r.final_status === "rejected"
                        ? "text-orange-400 border-orange-900/60 bg-orange-950/40"
                        : "text-red-400 border-red-900/60 bg-red-950/40"
                  }`}
                >
                  {r.final_status}
                </span>
                <span className="text-[11px] text-slate-600">
                  {shortDate(r.created_at)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                {(
                  [
                    ["Record ID", shortHash(r.record_id)],
                    ["Model", r.model_id],
                    ["Duration", `${r.inference_duration_ms}ms`],
                    ["Chain hash", shortHash(r.chain_hash)],
                  ] as const
                ).map(([k, v]) => (
                  <div key={k}>
                    <div className="text-[10px] text-slate-600">{k}</div>
                    <div className="hash text-[11px] text-slate-400">{v}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
