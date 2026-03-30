"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { triggerMarginDiagnosis } from "@/lib/api";
import type { MarginDiagnosisInput, WorkflowCase } from "@/lib/types";
import StatusBadge from "@/components/StatusBadge";

export default function MarginDiagnosisPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    billing_record_id: "",
    contract_id: "",
    period_start: "",
    period_end: "",
  });
  const [lineItemsText, setLineItemsText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<WorkflowCase | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      let lineItems: Record<string, unknown>[] = [];
      if (lineItemsText.trim()) {
        try {
          lineItems = JSON.parse(lineItemsText);
        } catch {
          setError("Line items must be valid JSON array");
          setSubmitting(false);
          return;
        }
      }
      const input: MarginDiagnosisInput = {
        billing_record_id: form.billing_record_id,
        contract_id: form.contract_id || undefined,
        line_items: lineItems.length > 0 ? lineItems : undefined,
        period_start: form.period_start || undefined,
        period_end: form.period_end || undefined,
      };
      const res = await triggerMarginDiagnosis(input);
      setResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to trigger workflow");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Margin Diagnosis</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Diagnose margin leakage from billing records against contract obligations.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 max-w-xl space-y-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700">Billing Record ID</label>
          <input
            type="text"
            required
            value={form.billing_record_id}
            onChange={(e) => setForm({ ...form, billing_record_id: e.target.value })}
            placeholder="e.g., BR-2024-001"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Contract ID</label>
          <input
            type="text"
            value={form.contract_id}
            onChange={(e) => setForm({ ...form, contract_id: e.target.value })}
            placeholder="UUID of the contract (optional)"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700">Period Start</label>
            <input
              type="datetime-local"
              value={form.period_start}
              onChange={(e) => setForm({ ...form, period_start: e.target.value })}
              className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-neutral-700">Period End</label>
            <input
              type="datetime-local"
              value={form.period_end}
              onChange={(e) => setForm({ ...form, period_end: e.target.value })}
              className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Line Items (JSON)</label>
          <textarea
            value={lineItemsText}
            onChange={(e) => setLineItemsText(e.target.value)}
            rows={4}
            placeholder='[{"description": "Service A", "amount": 1000}]'
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <button
          type="submit"
          disabled={submitting || !form.billing_record_id}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {submitting ? "Submitting..." : "Run Margin Diagnosis"}
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
