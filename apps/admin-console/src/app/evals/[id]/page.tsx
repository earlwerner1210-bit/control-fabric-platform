"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { format } from "date-fns";
import { getEvalRun } from "@/lib/api";
import type { EvalRun, EvalCase } from "@/lib/types";

export default function EvalRunDetailPage() {
  const params = useParams();
  const runId = params.id as string;

  const [run, setRun] = useState<EvalRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getEvalRun(runId);
        setRun(data);
      } catch (err: any) {
        setError(err?.response?.data?.detail ?? "Failed to load eval run");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [runId]);

  if (loading) {
    return <p className="py-12 text-center text-sm text-neutral-400">Loading eval run...</p>;
  }

  if (error || !run) {
    return (
      <div className="py-12 text-center">
        <p className="text-sm text-red-600">{error ?? "Eval run not found"}</p>
      </div>
    );
  }

  const passRate = run.total_cases > 0 ? ((run.passed_cases / run.total_cases) * 100).toFixed(1) : "0";

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">{run.name}</h1>
          <p className="mt-1 text-sm text-neutral-500">{run.description}</p>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
            run.status === "completed"
              ? "bg-green-100 text-green-700"
              : run.status === "running"
                ? "bg-blue-100 text-blue-700"
                : run.status === "failed"
                  ? "bg-red-100 text-red-700"
                  : "bg-neutral-100 text-neutral-600"
          }`}
        >
          {run.status}
        </span>
      </div>

      {/* Stats */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
        {[
          { label: "Domain Pack", value: run.domain_pack },
          { label: "Workflow", value: run.workflow_type.replace(/-/g, " ") },
          { label: "Model", value: run.model_name },
          { label: "Pass Rate", value: `${passRate}%` },
          { label: "Avg Latency", value: run.avg_latency_ms ? `${run.avg_latency_ms}ms` : "-" },
        ].map((s) => (
          <div key={s.label} className="rounded-lg border border-neutral-200 bg-white p-4">
            <p className="text-xs text-neutral-500">{s.label}</p>
            <p className="mt-1 text-lg font-semibold text-neutral-900">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Progress bar */}
      <div className="mt-6">
        <div className="flex items-center justify-between text-sm text-neutral-600">
          <span>
            <span className="font-medium text-green-600">{run.passed_cases}</span> passed,{" "}
            <span className="font-medium text-red-600">{run.failed_cases}</span> failed of{" "}
            <span className="font-medium">{run.total_cases}</span> total
          </span>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-neutral-200">
          <div
            className="h-full rounded-full bg-green-500 transition-all"
            style={{ width: `${passRate}%` }}
          />
        </div>
      </div>

      {/* Cases */}
      <div className="mt-8">
        <h2 className="text-lg font-medium text-neutral-900">Cases</h2>
        {!run.cases || run.cases.length === 0 ? (
          <p className="mt-4 text-sm text-neutral-400">No eval cases available.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {run.cases.map((evalCase) => (
              <div
                key={evalCase.id}
                className="rounded-lg border border-neutral-200 bg-white"
              >
                <button
                  onClick={() =>
                    setExpandedCase(expandedCase === evalCase.id ? null : evalCase.id)
                  }
                  className="flex w-full items-center justify-between px-4 py-3 text-left"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`h-2.5 w-2.5 rounded-full ${
                        evalCase.passed ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                    <span className="text-sm font-medium text-neutral-900">
                      Case {evalCase.case_id.slice(0, 8)}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        evalCase.passed
                          ? "bg-green-100 text-green-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {evalCase.passed ? "passed" : "failed"}
                    </span>
                  </div>
                  <div className="flex gap-3 text-xs text-neutral-500">
                    {Object.entries(evalCase.metrics).map(([key, val]) => (
                      <span key={key}>
                        {key}: {typeof val === "number" ? val.toFixed(2) : val}
                      </span>
                    ))}
                  </div>
                </button>
                {expandedCase === evalCase.id && (
                  <div className="border-t border-neutral-200 px-4 py-3 space-y-3">
                    {evalCase.notes && (
                      <p className="text-sm text-neutral-600">{evalCase.notes}</p>
                    )}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <h4 className="text-xs font-medium uppercase text-neutral-500">Expected</h4>
                        <pre className="mt-1 overflow-x-auto rounded bg-neutral-50 p-2 text-xs text-neutral-700">
                          {JSON.stringify(evalCase.expected, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <h4 className="text-xs font-medium uppercase text-neutral-500">Actual</h4>
                        <pre className="mt-1 overflow-x-auto rounded bg-neutral-50 p-2 text-xs text-neutral-700">
                          {JSON.stringify(evalCase.actual, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
