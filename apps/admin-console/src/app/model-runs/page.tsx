"use client";

import { useEffect, useState, useCallback } from "react";
import { format } from "date-fns";
import { listModelRuns } from "@/lib/api";
import type { ModelRun } from "@/lib/types";
import DataTable, { type Column } from "@/components/DataTable";

export default function ModelRunsPage() {
  const [runs, setRuns] = useState<ModelRun[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    model_name: "",
    status: "",
    workflow_type: "",
  });

  const loadRuns = useCallback(
    async (p: number) => {
      setLoading(true);
      try {
        const cleanFilters: Record<string, string> = {};
        if (filters.model_name) cleanFilters.model_name = filters.model_name;
        if (filters.status) cleanFilters.status = filters.status;
        if (filters.workflow_type) cleanFilters.workflow_type = filters.workflow_type;
        const res = await listModelRuns(p, cleanFilters);
        setRuns(res.items);
        setTotalPages(res.total_pages);
        setPage(res.page);
      } catch {
        // API not available
      } finally {
        setLoading(false);
      }
    },
    [filters]
  );

  useEffect(() => {
    loadRuns(1);
  }, [loadRuns]);

  const columns: Column<ModelRun>[] = [
    {
      header: "Model",
      accessor: (row) => (
        <div>
          <span className="font-medium">{row.model_name}</span>
          <span className="ml-1.5 text-xs text-neutral-400">{row.provider}</span>
        </div>
      ),
    },
    {
      header: "Workflow",
      accessor: (row) => row.workflow_type.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    },
    {
      header: "Status",
      accessor: (row) => (
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
            row.status === "success"
              ? "bg-green-100 text-green-700"
              : row.status === "error"
                ? "bg-red-100 text-red-700"
                : "bg-yellow-100 text-yellow-700"
          }`}
        >
          {row.status}
        </span>
      ),
    },
    {
      header: "Tokens",
      accessor: (row) => (
        <span className="text-xs">
          {row.input_tokens} in / {row.output_tokens} out
        </span>
      ),
    },
    {
      header: "Latency",
      accessor: (row) => `${row.latency_ms}ms`,
    },
    {
      header: "Case",
      accessor: (row) => <span className="font-mono text-xs">{row.case_id.slice(0, 8)}</span>,
    },
    {
      header: "Time",
      accessor: (row) => format(new Date(row.created_at), "MMM d, HH:mm:ss"),
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Model Runs</h1>
      <p className="mt-1 text-sm text-neutral-500">History of all LLM inference calls.</p>

      <div className="mt-6 flex gap-3">
        <input
          type="text"
          placeholder="Filter by model..."
          value={filters.model_name}
          onChange={(e) => setFilters({ ...filters, model_name: e.target.value })}
          className="rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          className="rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All statuses</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
          <option value="timeout">Timeout</option>
        </select>
        <select
          value={filters.workflow_type}
          onChange={(e) => setFilters({ ...filters, workflow_type: e.target.value })}
          className="rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All workflows</option>
          <option value="contract-compile">Contract Compile</option>
          <option value="work-order-readiness">Work Order Readiness</option>
          <option value="incident-dispatch">Incident Dispatch</option>
          <option value="margin-diagnosis">Margin Diagnosis</option>
        </select>
      </div>

      <div className="mt-4">
        {loading ? (
          <p className="text-sm text-neutral-400">Loading model runs...</p>
        ) : (
          <DataTable
            columns={columns}
            data={runs}
            page={page}
            totalPages={totalPages}
            onPageChange={loadRuns}
            emptyMessage="No model runs found."
          />
        )}
      </div>
    </div>
  );
}
