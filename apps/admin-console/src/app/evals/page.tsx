"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { listEvalRuns, triggerEvalRun } from "@/lib/api";
import type { EvalRun } from "@/lib/types";
import DataTable, { type Column } from "@/components/DataTable";

export default function EvalsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    domain_pack: "contract-margin",
    workflow_type: "contract-compile",
    model_name: "gpt-4",
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await listEvalRuns();
        setRuns(data);
      } catch {
        // API not available
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const run = await triggerEvalRun(form);
      setRuns((prev) => [run, ...prev]);
      setShowForm(false);
      setForm({ name: "", domain_pack: "contract-margin", workflow_type: "contract-compile", model_name: "gpt-4" });
    } catch {
      // handle error
    } finally {
      setSubmitting(false);
    }
  };

  const columns: Column<EvalRun>[] = [
    {
      header: "Name",
      accessor: (row) => <span className="font-medium">{row.name}</span>,
    },
    {
      header: "Status",
      accessor: (row) => (
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
            row.status === "completed"
              ? "bg-green-100 text-green-700"
              : row.status === "running"
                ? "bg-blue-100 text-blue-700"
                : row.status === "failed"
                  ? "bg-red-100 text-red-700"
                  : "bg-neutral-100 text-neutral-600"
          }`}
        >
          {row.status}
        </span>
      ),
    },
    { header: "Domain Pack", accessor: "domain_pack" },
    {
      header: "Workflow",
      accessor: (row) => row.workflow_type.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    },
    { header: "Model", accessor: "model_name" },
    {
      header: "Results",
      accessor: (row) => (
        <span className="text-xs">
          <span className="text-green-600">{row.passed_cases}</span> /{" "}
          <span>{row.total_cases}</span> passed
        </span>
      ),
    },
    {
      header: "Avg Latency",
      accessor: (row) => (row.avg_latency_ms ? `${row.avg_latency_ms}ms` : "-"),
    },
    {
      header: "Created",
      accessor: (row) => format(new Date(row.created_at), "MMM d, yyyy HH:mm"),
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Eval Runs</h1>
          <p className="mt-1 text-sm text-neutral-500">Run and review evaluations across models and workflows.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showForm ? "Cancel" : "New Eval Run"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleTrigger} className="mt-4 rounded-lg border border-neutral-200 bg-white p-5 max-w-xl space-y-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700">Name</label>
            <input
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g., GPT-4 contract compile eval"
              className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
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
            <div>
              <label className="block text-sm font-medium text-neutral-700">Workflow</label>
              <select
                value={form.workflow_type}
                onChange={(e) => setForm({ ...form, workflow_type: e.target.value })}
                className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="contract-compile">Contract Compile</option>
                <option value="work-order-readiness">Work Order Readiness</option>
                <option value="incident-dispatch">Incident Dispatch</option>
                <option value="margin-diagnosis">Margin Diagnosis</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700">Model</label>
              <input
                type="text"
                value={form.model_name}
                onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting || !form.name}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? "Triggering..." : "Trigger Eval Run"}
          </button>
        </form>
      )}

      <div className="mt-6">
        {loading ? (
          <p className="text-sm text-neutral-400">Loading eval runs...</p>
        ) : (
          <DataTable
            columns={columns}
            data={runs}
            onRowClick={(row) => router.push(`/evals/${row.id}`)}
            emptyMessage="No eval runs found."
          />
        )}
      </div>
    </div>
  );
}
