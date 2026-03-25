"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { triggerWorkOrderReadiness } from "@/lib/api";
import type { WorkOrderReadinessInput, WorkflowCase } from "@/lib/types";
import StatusBadge from "@/components/StatusBadge";

export default function WorkOrderReadinessPage() {
  const router = useRouter();
  const [form, setForm] = useState<WorkOrderReadinessInput>({
    work_order_id: "",
    control_object_ids: [],
    required_skills: [],
    dispatch_region: "",
  });
  const [skillsText, setSkillsText] = useState("");
  const [coIdsText, setCoIdsText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<WorkflowCase | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const input: WorkOrderReadinessInput = {
        work_order_id: form.work_order_id,
        control_object_ids: coIdsText ? coIdsText.split(",").map((s) => s.trim()).filter(Boolean) : [],
        required_skills: skillsText ? skillsText.split(",").map((s) => s.trim()).filter(Boolean) : [],
        dispatch_region: form.dispatch_region || undefined,
      };
      const res = await triggerWorkOrderReadiness(input);
      setResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to trigger workflow");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Work Order Readiness</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Verify that all prerequisites are met before dispatching a work order.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 max-w-xl space-y-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700">Work Order ID</label>
          <input
            type="text"
            required
            value={form.work_order_id}
            onChange={(e) => setForm({ ...form, work_order_id: e.target.value })}
            placeholder="e.g., WO-2024-001"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Control Object IDs</label>
          <input
            type="text"
            value={coIdsText}
            onChange={(e) => setCoIdsText(e.target.value)}
            placeholder="Comma-separated UUIDs (optional)"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Required Skills</label>
          <input
            type="text"
            value={skillsText}
            onChange={(e) => setSkillsText(e.target.value)}
            placeholder="Comma-separated skills (optional)"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">Dispatch Region</label>
          <input
            type="text"
            value={form.dispatch_region}
            onChange={(e) => setForm({ ...form, dispatch_region: e.target.value })}
            placeholder="e.g., US-EAST (optional)"
            className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <button
          type="submit"
          disabled={submitting || !form.work_order_id}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {submitting ? "Submitting..." : "Check Readiness"}
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
