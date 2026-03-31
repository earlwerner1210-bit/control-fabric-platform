"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/layout/shell";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const RISK_OPTIONS = [
  { value: "low", label: "Low", description: "Minor change, easy rollback" },
  { value: "medium", label: "Medium", description: "Moderate impact, tested" },
  { value: "high", label: "High", description: "Significant change, affects many users" },
  { value: "critical", label: "Critical", description: "Core system change, maximum scrutiny" },
];

const WORKSPACE_ID = "demo-workspace";

export default function NewReleasePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [form, setForm] = useState({
    title: "", service_name: "", environment: "production",
    risk_level: "medium", description: "",
  });
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () => api.createRelease({ ...form, workspace_id: WORKSPACE_ID, submitted_by: "you@company.com" }),
    onSuccess: (data: any) => {
      qc.invalidateQueries({ queryKey: ["releases"] });
      router.push(`/releases/${data.release_id}`);
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <Shell>
      <div className="max-w-xl">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-slate-800">New release request</h1>
          <p className="text-sm text-slate-500 mt-0.5">Tell us what you're releasing and how risky it is.</p>
        </div>

        <div className="space-y-5">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Release title</label>
            <input value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))}
              placeholder="e.g. Payment API v2.1 — production release"
              className="w-full border border-border rounded-lg px-3 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
          </div>

          {/* Service */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Service or component</label>
            <input value={form.service_name} onChange={e => setForm(p => ({ ...p, service_name: e.target.value }))}
              placeholder="e.g. payment-api, auth-service, frontend"
              className="w-full border border-border rounded-lg px-3 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
          </div>

          {/* Risk */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">How risky is this release?</label>
            <div className="grid grid-cols-2 gap-2">
              {RISK_OPTIONS.map(opt => (
                <button key={opt.value}
                  onClick={() => setForm(p => ({ ...p, risk_level: opt.value }))}
                  className={cn(
                    "text-left p-3 rounded-lg border transition-all",
                    form.risk_level === opt.value
                      ? "border-brand bg-brand/5 ring-1 ring-brand/20"
                      : "border-border bg-white hover:bg-surface-raised"
                  )}>
                  <p className="text-sm font-semibold text-slate-700">{opt.label}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{opt.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              What's changing? <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <textarea value={form.description}
              onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
              rows={3} placeholder="Brief description of the change..."
              className="w-full border border-border rounded-lg px-3 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand resize-none" />
          </div>

          {error && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">{error}</p>}

          <div className="flex gap-3 pt-1">
            <Button onClick={() => create.mutate()} disabled={!form.title || !form.service_name || create.isPending}>
              {create.isPending ? "Creating..." : "Create release →"}
            </Button>
            <Button variant="secondary" onClick={() => router.back()}>Cancel</Button>
          </div>
        </div>
      </div>
    </Shell>
  );
}
