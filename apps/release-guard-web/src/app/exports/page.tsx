"use client";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/layout/shell";
import { Button } from "@/components/ui/button";
import { timeAgo } from "@/lib/utils";

const WORKSPACE_ID = "demo-workspace";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const rg = (path: string, opts?: RequestInit) =>
  fetch(`${API}/rg${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  }).then(r => r.json());

const EXPORT_TYPES = [
  {
    type: "releases",
    label: "Release decisions",
    description: "All releases with status, evidence, and decision timestamps",
    icon: "▶",
  },
  {
    type: "approvals",
    label: "Approval records",
    description: "All approval decisions with approver, note, and timing",
    icon: "✓",
  },
  {
    type: "exceptions",
    label: "Exception log",
    description: "All emergency exceptions with justifications and outcomes",
    icon: "⚠",
  },
];

export default function ExportsPage() {
  const [exporting, setExporting] = useState<string | null>(null);
  const [lastExportId, setLastExportId] = useState<string | null>(null);

  const { data: jobs, refetch } = useQuery({
    queryKey: ["exports", WORKSPACE_ID],
    queryFn: () => rg(`/exports?workspace_id=${WORKSPACE_ID}`),
  });

  const createExport = useMutation({
    mutationFn: ({ type }: { type: string }) =>
      rg(`/exports/${type}`, {
        method: "POST",
        body: JSON.stringify({
          workspace_id: WORKSPACE_ID,
          requested_by: "you@company.com",
          format: "csv",
        }),
      }),
    onSuccess: (data: any) => {
      setLastExportId(data.export_id);
      setExporting(null);
      refetch();
    },
  });

  const exportList = (jobs as any)?.exports ?? [];

  return (
    <Shell>
      <div className="max-w-2xl space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-800">Audit exports</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Download compliance evidence for auditors and regulators
          </p>
        </div>

        {/* Export types */}
        <div className="space-y-3">
          {EXPORT_TYPES.map(({ type, label, description, icon }) => (
            <div key={type}
              className="bg-white rounded-xl border border-slate-200 p-5 flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center text-lg shrink-0">
                {icon}
              </div>
              <div className="flex-1">
                <p className="font-semibold text-sm text-slate-700">{label}</p>
                <p className="text-xs text-slate-400 mt-0.5">{description}</p>
              </div>
              <Button variant="secondary" size="sm"
                disabled={createExport.isPending && exporting === type}
                onClick={() => { setExporting(type); createExport.mutate({ type }); }}>
                {createExport.isPending && exporting === type ? "Generating..." : "Export CSV"}
              </Button>
            </div>
          ))}
        </div>

        {/* Download latest */}
        {lastExportId && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3">
            <span className="text-green-600 text-lg">✓</span>
            <div className="flex-1">
              <p className="text-sm font-semibold text-green-800">Export ready</p>
              <p className="text-xs text-green-600 mt-0.5">Your export has been generated</p>
            </div>
            <a href={`${API}/rg/exports/${lastExportId}/download`}
              target="_blank"
              className="text-sm font-medium text-green-700 underline">
              Download
            </a>
          </div>
        )}

        {/* History */}
        {exportList.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Export history</h2>
            <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
              {exportList.map((job: any) => (
                <div key={job.export_id}
                  className="flex items-center gap-4 px-5 py-3.5">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-700 capitalize">
                      {job.export_type} — {job.record_count} records
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {job.format.toUpperCase()} · {timeAgo(job.requested_at)}
                    </p>
                  </div>
                  <a href={`${API}/rg/exports/${job.export_id}/download`}
                    target="_blank"
                    className="text-xs font-medium text-indigo-600 hover:underline">
                    Download
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
