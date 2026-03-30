"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { format } from "date-fns";
import { getCase, getCaseAudit, getCaseValidations, getCaseControlObjects } from "@/lib/api";
import type { WorkflowCase, AuditEvent, ValidationResult, ControlObject } from "@/lib/types";
import StatusBadge from "@/components/StatusBadge";
import AuditTimeline from "@/components/AuditTimeline";

type Tab = "overview" | "control-objects" | "audit" | "validations";

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = params.id as string;

  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [workflowCase, setWorkflowCase] = useState<WorkflowCase | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [validations, setValidations] = useState<ValidationResult[]>([]);
  const [controlObjects, setControlObjects] = useState<ControlObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [caseData, audit, vals, cos] = await Promise.all([
          getCase(caseId),
          getCaseAudit(caseId),
          getCaseValidations(caseId),
          getCaseControlObjects(caseId),
        ]);
        setWorkflowCase(caseData);
        setAuditEvents(audit);
        setValidations(vals);
        setControlObjects(cos);
      } catch (err: any) {
        setError(err?.response?.data?.detail ?? "Failed to load case");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [caseId]);

  if (loading) {
    return <p className="py-12 text-center text-sm text-neutral-400">Loading case...</p>;
  }

  if (error || !workflowCase) {
    return (
      <div className="py-12 text-center">
        <p className="text-sm text-red-600">{error ?? "Case not found"}</p>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: "overview", label: "Overview" },
    { key: "control-objects", label: "Control Objects", count: controlObjects.length },
    { key: "audit", label: "Audit Trail", count: auditEvents.length },
    { key: "validations", label: "Validations", count: validations.length },
  ];

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">
            {workflowCase.workflow_type.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </h1>
          <p className="mt-1 text-sm font-mono text-neutral-500">{workflowCase.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={workflowCase.status} />
          {workflowCase.verdict && <StatusBadge status={workflowCase.verdict} />}
        </div>
      </div>

      <div className="mt-4 flex gap-4 text-xs text-neutral-500">
        <span>Created: {format(new Date(workflowCase.created_at), "MMM d, yyyy HH:mm:ss")}</span>
        {workflowCase.started_at && (
          <span>Started: {format(new Date(workflowCase.started_at), "MMM d, yyyy HH:mm:ss")}</span>
        )}
        {workflowCase.completed_at && (
          <span>Completed: {format(new Date(workflowCase.completed_at), "MMM d, yyyy HH:mm:ss")}</span>
        )}
      </div>

      {workflowCase.error_detail && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {workflowCase.error_detail}
        </div>
      )}

      {/* Tabs */}
      <div className="mt-6 border-b border-neutral-200">
        <nav className="-mb-px flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`whitespace-nowrap border-b-2 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-neutral-500 hover:border-neutral-300 hover:text-neutral-700"
              }`}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span className="ml-2 rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === "overview" && <OverviewTab workflowCase={workflowCase} />}
        {activeTab === "control-objects" && <ControlObjectsTab objects={controlObjects} />}
        {activeTab === "audit" && <AuditTimeline events={auditEvents} />}
        {activeTab === "validations" && <ValidationsTab validations={validations} />}
      </div>
    </div>
  );
}

function OverviewTab({ workflowCase }: { workflowCase: WorkflowCase }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-neutral-900">Input Payload</h3>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-neutral-50 border border-neutral-200 p-4 text-xs text-neutral-700">
          {JSON.stringify(workflowCase.input_payload, null, 2)}
        </pre>
      </div>
      {workflowCase.output_payload && (
        <div>
          <h3 className="text-sm font-medium text-neutral-900">Output Payload</h3>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-neutral-50 border border-neutral-200 p-4 text-xs text-neutral-700">
            {JSON.stringify(workflowCase.output_payload, null, 2)}
          </pre>
        </div>
      )}
      {Object.keys(workflowCase.metadata).length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-neutral-900">Metadata</h3>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-neutral-50 border border-neutral-200 p-4 text-xs text-neutral-700">
            {JSON.stringify(workflowCase.metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function ControlObjectsTab({ objects }: { objects: ControlObject[] }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  if (objects.length === 0) {
    return <p className="py-8 text-center text-sm text-neutral-400">No control objects linked to this case.</p>;
  }

  return (
    <div className="space-y-3">
      {objects.map((obj) => (
        <div key={obj.id} className="rounded-lg border border-neutral-200 bg-white">
          <button
            onClick={() => setExpanded((prev) => ({ ...prev, [obj.id]: !prev[obj.id] }))}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <div className="flex items-center gap-3">
              <span className="rounded bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">
                {obj.control_type}
              </span>
              <span className="text-sm font-medium text-neutral-900">{obj.label}</span>
              {obj.confidence !== null && (
                <span className="text-xs text-neutral-400">{(obj.confidence * 100).toFixed(0)}% confidence</span>
              )}
            </div>
            <span className="text-xs text-neutral-400">{expanded[obj.id] ? "Collapse" : "Expand"}</span>
          </button>
          {expanded[obj.id] && (
            <div className="border-t border-neutral-200 px-4 py-3">
              {obj.description && (
                <p className="mb-2 text-sm text-neutral-600">{obj.description}</p>
              )}
              <pre className="overflow-x-auto rounded bg-neutral-50 p-3 text-xs text-neutral-700">
                {JSON.stringify(obj.payload, null, 2)}
              </pre>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ValidationsTab({ validations }: { validations: ValidationResult[] }) {
  if (validations.length === 0) {
    return <p className="py-8 text-center text-sm text-neutral-400">No validation results for this case.</p>;
  }

  return (
    <div className="space-y-3">
      {validations.map((val) => (
        <div key={val.id} className="rounded-lg border border-neutral-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <StatusBadge status={val.status} />
              <span className="text-sm text-neutral-700">
                {val.target_type} / {val.target_id.slice(0, 8)}
              </span>
            </div>
            <div className="flex gap-3 text-xs text-neutral-500">
              <span className="text-green-600">{val.rules_passed} passed</span>
              <span className="text-yellow-600">{val.rules_warned} warned</span>
              <span className="text-red-600">{val.rules_blocked} blocked</span>
            </div>
          </div>
          {val.rule_results.length > 0 && (
            <div className="mt-3 space-y-1">
              {val.rule_results.map((rule, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 rounded px-2 py-1 text-xs"
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      rule.passed ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                  <span className="font-medium text-neutral-700">{rule.rule_name}</span>
                  <span className="text-neutral-500">{rule.message}</span>
                  <span className={`ml-auto rounded px-1.5 py-0.5 text-xs ${
                    rule.severity === "critical" ? "bg-red-100 text-red-700" :
                    rule.severity === "error" ? "bg-red-50 text-red-600" :
                    rule.severity === "warning" ? "bg-yellow-100 text-yellow-700" :
                    "bg-neutral-100 text-neutral-500"
                  }`}>
                    {rule.severity}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
