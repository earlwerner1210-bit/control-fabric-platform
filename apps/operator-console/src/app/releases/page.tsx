"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

export default function ReleasesPage() {
  const [form, setForm] = useState({
    release_name: "",
    environment: "staging",
    requested_by: "",
    evidence: "",
    origin: "human_operator",
  });
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const submit = useMutation({
    mutationFn: async () => {
      const res = await fetch("http://localhost:8000/reconciliation/run", {
        method: "POST",
      });
      return res.json();
    },
    onSuccess: (data: Record<string, unknown>) => setResult(data),
  });

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      <div>
        <h1 className="text-[15px] font-semibold text-slate-200">
          Release Gate
        </h1>
        <p className="text-[12px] text-slate-500 mt-0.5">
          Submit a release for evidence-gated validation
        </p>
      </div>

      <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5 space-y-4">
        <div className="text-[11px] text-[#00e5b4] uppercase tracking-wider">
          New release submission
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="text-[11px] text-slate-500 block mb-1">
              Release name
            </label>
            <input
              value={form.release_name}
              onChange={(e) =>
                setForm((f) => ({ ...f, release_name: e.target.value }))
              }
              placeholder="API Gateway v2.4.1"
              className="w-full bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4]"
            />
          </div>
          <div>
            <label className="text-[11px] text-slate-500 block mb-1">
              Environment
            </label>
            <select
              value={form.environment}
              onChange={(e) =>
                setForm((f) => ({ ...f, environment: e.target.value }))
              }
              className="w-full bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 focus:outline-none focus:border-[#00e5b4]"
            >
              <option value="staging">Staging</option>
              <option value="production">Production</option>
              <option value="hotfix">Hotfix</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] text-slate-500 block mb-1">
              Requested by
            </label>
            <input
              value={form.requested_by}
              onChange={(e) =>
                setForm((f) => ({ ...f, requested_by: e.target.value }))
              }
              placeholder="engineer@company.com"
              className="w-full bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4]"
            />
          </div>
          <div className="col-span-2">
            <label className="text-[11px] text-slate-500 block mb-1">
              Evidence references (comma-separated)
            </label>
            <input
              value={form.evidence}
              onChange={(e) =>
                setForm((f) => ({ ...f, evidence: e.target.value }))
              }
              placeholder="ci-run-001, security-scan-passed, load-test-approved"
              className="w-full bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4]"
            />
            <div className="text-[10px] text-slate-600 mt-1">
              Leave empty to test blocking behaviour
            </div>
          </div>
        </div>

        <button
          onClick={() => submit.mutate()}
          disabled={submit.isPending || !form.release_name}
          className="w-full py-2.5 text-[12px] bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430] rounded hover:bg-[#00e5b425] transition-colors disabled:opacity-40"
        >
          {submit.isPending
            ? "Submitting to release gate..."
            : "Submit to release gate"}
        </button>
      </div>

      {result && (
        <div className="bg-[#0a1a12] border border-emerald-900/40 rounded-lg p-4">
          <div className="text-[11px] text-emerald-400 uppercase tracking-wider mb-2">
            Gate response
          </div>
          <pre className="text-[11px] text-slate-400 overflow-x-auto">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}

      <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 space-y-3">
        <div className="text-[11px] text-slate-500 uppercase tracking-wider">
          How the gate works
        </div>
        {(
          [
            ["1. Completeness", "All required fields must be present"],
            [
              "2. Evidence sufficiency",
              "AI-originated actions require evidence references",
            ],
            [
              "3. Policy compliance",
              "Action type must not be blocked by active policy",
            ],
            [
              "4. Provenance integrity",
              "Request hash must be intact",
            ],
            [
              "5. Schema conformance",
              "Payload must conform to expected schema",
            ],
          ] as const
        ).map(([k, v]) => (
          <div key={k} className="flex gap-3 text-[11px]">
            <span className="text-[#00e5b4] flex-shrink-0 w-28">{k}</span>
            <span className="text-slate-500">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
