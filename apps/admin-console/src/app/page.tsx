"use client";

import { useEffect, useState } from "react";
import { MessageSquareText, Package, Activity, FlaskConical } from "lucide-react";
import { listPromptTemplates, listDomainPackVersions, listEvalRuns } from "@/lib/api";

interface Stat {
  label: string;
  value: number | string;
  icon: React.ElementType;
  color: string;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<Stat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [prompts, packs, evals] = await Promise.all([
          listPromptTemplates(),
          listDomainPackVersions(),
          listEvalRuns(),
        ]);
        setStats([
          {
            label: "Prompt Templates",
            value: prompts.length,
            icon: MessageSquareText,
            color: "bg-blue-50 text-blue-600",
          },
          {
            label: "Domain Pack Versions",
            value: packs.length,
            icon: Package,
            color: "bg-amber-50 text-amber-600",
          },
          {
            label: "Active Packs",
            value: packs.filter((p) => p.is_active).length,
            icon: Package,
            color: "bg-green-50 text-green-600",
          },
          {
            label: "Eval Runs",
            value: evals.length,
            icon: FlaskConical,
            color: "bg-purple-50 text-purple-600",
          },
        ]);
      } catch {
        setStats([
          { label: "Prompt Templates", value: "-", icon: MessageSquareText, color: "bg-blue-50 text-blue-600" },
          { label: "Domain Pack Versions", value: "-", icon: Package, color: "bg-amber-50 text-amber-600" },
          { label: "Active Packs", value: "-", icon: Package, color: "bg-green-50 text-green-600" },
          { label: "Eval Runs", value: "-", icon: FlaskConical, color: "bg-purple-50 text-purple-600" },
        ]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Admin Dashboard</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Manage prompts, domain packs, model runs, and evaluations.
      </p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
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
    </div>
  );
}
