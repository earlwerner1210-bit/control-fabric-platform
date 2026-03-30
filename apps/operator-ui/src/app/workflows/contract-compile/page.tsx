"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { triggerContractCompile } from "@/lib/api";
import type { ContractCompileInput, WorkflowCase } from "@/lib/types";
import StatusBadge from "@/components/StatusBadge";

export default function ContractCompilePage() {
  const router = useRouter();
  const [form, setForm] = useState<ContractCompileInput>({
    document_id: "",
    domain_pack: "contract-margin",
    extract_obligations: true,
    extract_penalties: true,
    extract_billing: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<WorkflowCase | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await triggerContractCompile(form);
      setResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to trigger workflow");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Contract Compile</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Extract obligations, penalties, and billing terms from a contract document.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 max-w-xl space-y-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700">Document ID</label>
          <input
            type="text"
            required
            value={form.document_id}
            onChange={(e) => setForm({ ...form, document_id: e.target.value })}
            placeholder="UUID of the uploaded document"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Domain Pack</label>
          <select
            value={form.domain_pack}
            onChange={(e) => setForm({ ...form, domain_pack: e.target.value })}
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="contract-margin">contract-margin</option>
            <option value="utilities-field">utilities-field</option>
            <option value="telco-ops">telco-ops</option>
          </select>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-neutral-700">Extraction Options</label>
          {(["extract_obligations", "extract_penalties", "extract_billing"] as const).map((field) => (
            <label key={field} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form[field]}
                onChange={(e) => setForm({ ...form, [field]: e.target.checked })}
                className="rounded border-neutral-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-neutral-700">{field.replace("extract_", "").replace(/\b\w/g, (c) => c.toUpperCase())}</span>
            </label>
          ))}
        </div>

        <button
          type="submit"
          disabled={submitting || !form.document_id}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {submitting ? "Submitting..." : "Run Contract Compile"}
        </button>
      </form>

      {error && (
        <div className="mt-4 max-w-xl rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 max-w-xl rounded-lg border border-neutral-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-neutral-900">Workflow Case Created</h3>
            <StatusBadge status={result.status} />
          </div>
          <p className="mt-2 text-xs font-mono text-neutral-500">ID: {result.id}</p>
          <button
            onClick={() => router.push(`/cases/${result.id}`)}
            className="mt-3 text-sm font-medium text-blue-600 hover:text-blue-500"
          >
            View Case Details
          </button>
        </div>
      )}
    </div>
  );
}
