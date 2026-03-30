"use client";
import { Case, api } from "@/lib/api";
import {
  severityColor,
  statusColor,
  caseTypeColor,
  relativeTime,
  shortHash,
  cn,
} from "@/lib/utils";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function CaseCard({
  c,
  expanded = false,
}: {
  c: Case;
  expanded?: boolean;
}) {
  const [open, setOpen] = useState(expanded);
  const [resolveMode, setResolveMode] = useState(false);
  const [note, setNote] = useState("");
  const qc = useQueryClient();

  const resolve = useMutation({
    mutationFn: () => api.resolveCase(c.case_id, "operator", note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cases"] });
      setResolveMode(false);
    },
  });

  return (
    <div
      className={cn(
        "border rounded-lg bg-[#111318] transition-all",
        c.severity === "critical"
          ? "border-red-900/60 pulse-critical"
          : "border-[#1e2330]"
      )}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-[#ffffff04] transition-colors"
      >
        <span
          className={cn(
            "text-[10px] font-semibold px-2 py-0.5 rounded border mt-0.5 uppercase tracking-wider flex-shrink-0",
            severityColor(c.severity)
          )}
        >
          {c.severity}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "text-[11px] uppercase tracking-wide font-semibold",
                caseTypeColor(c.case_type)
              )}
            >
              {c.case_type}
            </span>
            {c.violated_rule_id && (
              <span className="text-[10px] text-slate-600 font-mono">
                {c.violated_rule_id}
              </span>
            )}
          </div>
          <div className="text-[12px] text-slate-300 mt-0.5 truncate">
            {c.title}
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span
              className={cn(
                "text-[10px] border rounded px-1.5 py-0.5",
                statusColor(c.status)
              )}
            >
              {c.status}
            </span>
            <span className="text-[10px] text-slate-600">
              {relativeTime(c.detected_at)}
            </span>
            <span className="text-[10px] text-slate-600">
              {c.affected_planes.join(" · ")}
            </span>
          </div>
        </div>
        <span className="text-slate-600 text-[11px] mt-1 flex-shrink-0">
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open && (
        <div className="border-t border-[#1e2330] px-4 pb-4 pt-3 space-y-3">
          <p className="text-[12px] text-slate-400 leading-relaxed">
            {c.description}
          </p>

          {c.remediation_suggestions.length > 0 && (
            <div className="space-y-1">
              <div className="text-[10px] text-[#00e5b4] uppercase tracking-wider">
                Remediation
              </div>
              {c.remediation_suggestions.map((s, i) => (
                <div key={i} className="text-[11px] text-slate-400 flex gap-2">
                  <span className="text-[#00e5b4] flex-shrink-0">→</span>
                  <span>{s}</span>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-4 pt-1">
            <div>
              <div className="text-[10px] text-slate-600">Case hash</div>
              <div className="hash">{shortHash(c.case_hash)}</div>
            </div>
            <div>
              <div className="text-[10px] text-slate-600">Severity score</div>
              <div className="text-[12px] text-slate-300">
                {c.severity_score}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-slate-600">Affected objects</div>
              <div className="text-[12px] text-slate-300">
                {c.affected_objects.length}
              </div>
            </div>
          </div>

          {!resolveMode && c.status === "open" && (
            <div className="flex gap-2 pt-1">
              <button
                onClick={() => setResolveMode(true)}
                className="text-[11px] px-3 py-1.5 bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430] rounded hover:bg-[#00e5b425] transition-colors"
              >
                Mark Resolved
              </button>
            </div>
          )}

          {resolveMode && (
            <div className="space-y-2 pt-1">
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Resolution note (required)..."
                className="w-full bg-[#0a0c10] border border-[#252d3d] rounded p-2 text-[12px] text-slate-300 placeholder-slate-600 resize-none h-16 focus:outline-none focus:border-[#00e5b4]"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => resolve.mutate()}
                  disabled={note.length < 5 || resolve.isPending}
                  className="text-[11px] px-3 py-1.5 bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430] rounded disabled:opacity-40 hover:bg-[#00e5b425] transition-colors"
                >
                  {resolve.isPending ? "Resolving..." : "Confirm"}
                </button>
                <button
                  onClick={() => setResolveMode(false)}
                  className="text-[11px] px-3 py-1.5 text-slate-500 border border-[#1e2330] rounded hover:text-slate-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
