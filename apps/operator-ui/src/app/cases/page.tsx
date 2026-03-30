"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { listCases } from "@/lib/api";
import type { WorkflowCase } from "@/lib/types";
import DataTable, { type Column } from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

const WORKFLOW_TYPES = [
  { value: "", label: "All workflows" },
  { value: "contract-compile", label: "Contract Compile" },
  { value: "work-order-readiness", label: "Work Order Readiness" },
  { value: "incident-dispatch", label: "Incident Dispatch" },
  { value: "margin-diagnosis", label: "Margin Diagnosis" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

export default function CasesPage() {
  const router = useRouter();
  const [cases, setCases] = useState<WorkflowCase[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [workflowFilter, setWorkflowFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const loadCases = useCallback(
    async (p: number) => {
      setLoading(true);
      try {
        const res = await listCases(
          p,
          statusFilter || undefined,
          workflowFilter || undefined
        );
        setCases(res.items);
        setTotalPages(res.total_pages);
        setPage(res.page);
      } catch {
        // API not yet available
      } finally {
        setLoading(false);
      }
    },
    [statusFilter, workflowFilter]
  );

  useEffect(() => {
    loadCases(1);
  }, [loadCases]);

  const columns: Column<WorkflowCase>[] = [
    {
      header: "ID",
      accessor: (row) => <span className="font-mono text-xs">{row.id.slice(0, 8)}</span>,
    },
    {
      header: "Workflow",
      accessor: (row) => (
        <span className="font-medium">
          {row.workflow_type.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
        </span>
      ),
    },
    {
      header: "Status",
      accessor: (row) => <StatusBadge status={row.status} />,
    },
    {
      header: "Verdict",
      accessor: (row) =>
        row.verdict ? <StatusBadge status={row.verdict} /> : <span className="text-neutral-400">-</span>,
    },
    {
      header: "Created",
      accessor: (row) => format(new Date(row.created_at), "MMM d, yyyy HH:mm"),
    },
    {
      header: "Completed",
      accessor: (row) =>
        row.completed_at
          ? format(new Date(row.completed_at), "MMM d, yyyy HH:mm")
          : "-",
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Cases</h1>
      <p className="mt-1 text-sm text-neutral-500">View and filter all workflow cases.</p>

      <div className="mt-6 flex gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          value={workflowFilter}
          onChange={(e) => setWorkflowFilter(e.target.value)}
          className="rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          {WORKFLOW_TYPES.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4">
        {loading ? (
          <p className="text-sm text-neutral-400">Loading cases...</p>
        ) : (
          <DataTable
            columns={columns}
            data={cases}
            page={page}
            totalPages={totalPages}
            onPageChange={loadCases}
            onRowClick={(row) => router.push(`/cases/${row.id}`)}
            emptyMessage="No cases found."
          />
        )}
      </div>
    </div>
  );
}
