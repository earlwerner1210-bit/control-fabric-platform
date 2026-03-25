"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { triggerIncidentDispatch } from "@/lib/api";
import type { IncidentDispatchInput, WorkflowCase } from "@/lib/types";
import StatusBadge from "@/components/StatusBadge";

export default function IncidentDispatchPage() {
  const router = useRouter();
  const [form, setForm] = useState<IncidentDispatchInput>({
    incident_id: "",
    severity: 3,
    category: "",
    region: "",
    description: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<WorkflowCase | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const input: IncidentDispatchInput = {
        incident_id: form.incident_id,
        severity: form.severity,
        category: form.category,
        region: form.region || undefined,
        description: form.description || undefined,
      };
      const res = await triggerIncidentDispatch(input);
      setResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to trigger workflow");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Incident Dispatch</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Route incidents to the correct team with SLA targets and escalation.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 max-w-xl space-y-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700">Incident ID</label>
          <input
            type="text"
            required
            value={form.incident_id}
            onChange={(e) => setForm({ ...form, incident_id: e.target.value })}
            placeholder="e.g., INC-2024-001"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Severity (1-5)</label>
          <select
            value={form.severity}
            onChange={(e) => setForm({ ...form, severity: parseInt(e.target.value) })}
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n} - {["Critical", "High", "Medium", "Low", "Informational"][n - 1]}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Category</label>
          <input
            type="text"
            required
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            placeholder="e.g., network-outage, billing-error"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Region</label>
          <input
            type="text"
            value={form.region}
            onChange={(e) => setForm({ ...form, region: e.target.value })}
            placeholder="e.g., US-WEST (optional)"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={3}
            placeholder="Describe the incident (optional)"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <button
          type="submit"
          disabled={submitting || !form.incident_id || !form.category}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {submitting ? "Submitting..." : "Dispatch Incident"}
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
