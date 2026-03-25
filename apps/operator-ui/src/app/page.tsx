"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { FileText, Workflow, CheckCircle, AlertTriangle } from "lucide-react";
import { listCases } from "@/lib/api";
import type { WorkflowCase, PaginatedResponse } from "@/lib/types";
import StatusBadge from "@/components/StatusBadge";
import CaseCard from "@/components/CaseCard";

interface StatCard {
  label: string;
  value: number;
  icon: React.ElementType;
  color: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [cases, setCases] = useState<WorkflowCase[]>([]);
  const [stats, setStats] = useState({ total: 0, pending: 0, completed: 0, failed: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await listCases(1);
        setCases(res.items.slice(0, 8));
        setStats({
          total: res.total,
          pending: res.items.filter((c) => c.status === "pending" || c.status === "running").length,
          completed: res.items.filter((c) => c.status === "completed").length,
          failed: res.items.filter((c) => c.status === "failed").length,
        });
      } catch {
        // API not available yet
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const statCards: StatCard[] = [
    { label: "Total Cases", value: stats.total, icon: FileText, color: "bg-blue-50 text-blue-600" },
    { label: "Pending", value: stats.pending, icon: Workflow, color: "bg-yellow-50 text-yellow-600" },
    { label: "Completed", value: stats.completed, icon: CheckCircle, color: "bg-green-50 text-green-600" },
    { label: "Failed", value: stats.failed, icon: AlertTriangle, color: "bg-red-50 text-red-600" },
  ];

  const workflows = [
    { key: "contract-compile", label: "Contract Compile", desc: "Extract obligations, penalties, billing from contracts" },
    { key: "work-order-readiness", label: "Work Order Readiness", desc: "Verify readiness for work order dispatch" },
    { key: "incident-dispatch", label: "Incident Dispatch", desc: "Route and escalate incidents" },
    { key: "margin-diagnosis", label: "Margin Diagnosis", desc: "Diagnose margin leakage and billing issues" },
  ];

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>
      <p className="mt-1 text-sm text-neutral-500">Overview of your control fabric operations.</p>

      {/* Stats */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((s) => (
          <div key={s.label} className="rounded-lg border border-neutral-200 bg-white p-5">
            <div className="flex items-center gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${s.color}`}>
                <s.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-neutral-500">{s.label}</p>
                <p className="text-2xl font-semibold text-neutral-900">
                  {loading ? "-" : s.value}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="mt-8">
        <h2 className="text-lg font-medium text-neutral-900">Quick Actions</h2>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {workflows.map((w) => (
            <button
              key={w.key}
              onClick={() => router.push(`/workflows/${w.key}`)}
              className="rounded-lg border border-neutral-200 bg-white p-4 text-left transition-shadow hover:shadow-md"
            >
              <p className="text-sm font-medium text-neutral-900">{w.label}</p>
              <p className="mt-1 text-xs text-neutral-500">{w.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Recent Cases */}
      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-neutral-900">Recent Cases</h2>
          <button
            onClick={() => router.push("/cases")}
            className="text-sm font-medium text-blue-600 hover:text-blue-500"
          >
            View all
          </button>
        </div>
        {loading ? (
          <p className="mt-4 text-sm text-neutral-400">Loading...</p>
        ) : cases.length === 0 ? (
          <p className="mt-4 text-sm text-neutral-400">No cases yet. Trigger a workflow to get started.</p>
        ) : (
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {cases.map((c) => (
              <CaseCard key={c.id} workflowCase={c} onClick={() => router.push(`/cases/${c.id}`)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
