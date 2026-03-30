"use client";

import { useRouter } from "next/navigation";
import { FileSearch, HardHat, Siren, DollarSign } from "lucide-react";

const workflows = [
  {
    key: "contract-compile",
    label: "Contract Compile",
    description:
      "Extract obligations, penalties, and billing terms from uploaded contracts. Creates structured control objects for downstream validation.",
    icon: FileSearch,
    color: "bg-blue-50 text-blue-600",
  },
  {
    key: "work-order-readiness",
    label: "Work Order Readiness",
    description:
      "Verify that all prerequisites are met before dispatching a work order. Checks skills, materials, and dispatch conditions.",
    icon: HardHat,
    color: "bg-amber-50 text-amber-600",
  },
  {
    key: "incident-dispatch",
    label: "Incident Dispatch",
    description:
      "Route incidents to the correct team based on severity, category, and region. Determines SLA targets and escalation levels.",
    icon: Siren,
    color: "bg-red-50 text-red-600",
  },
  {
    key: "margin-diagnosis",
    label: "Margin Diagnosis",
    description:
      "Diagnose margin leakage from billing records. Identifies under-recovery, penalty risks, and revenue assurance issues.",
    icon: DollarSign,
    color: "bg-green-50 text-green-600",
  },
];

export default function WorkflowsPage() {
  const router = useRouter();

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Workflows</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Select a workflow to launch. Each workflow processes inputs through the control fabric pipeline.
      </p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {workflows.map((w) => (
          <button
            key={w.key}
            onClick={() => router.push(`/workflows/${w.key}`)}
            className="flex items-start gap-4 rounded-lg border border-neutral-200 bg-white p-6 text-left transition-shadow hover:shadow-md"
          >
            <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg ${w.color}`}>
              <w.icon className="h-6 w-6" />
            </div>
            <div>
              <p className="text-base font-medium text-neutral-900">{w.label}</p>
              <p className="mt-1 text-sm text-neutral-500">{w.description}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
