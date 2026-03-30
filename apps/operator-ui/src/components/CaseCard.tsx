import { format } from "date-fns";
import StatusBadge from "./StatusBadge";
import type { WorkflowCase } from "@/lib/types";

interface CaseCardProps {
  workflowCase: WorkflowCase;
  onClick?: () => void;
}

export default function CaseCard({ workflowCase, onClick }: CaseCardProps) {
  return (
    <div
      onClick={onClick}
      className="cursor-pointer rounded-lg border border-neutral-200 bg-white p-4 transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-neutral-900">
            {workflowCase.workflow_type.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </p>
          <p className="mt-0.5 text-xs text-neutral-500 font-mono">
            {workflowCase.id.slice(0, 8)}
          </p>
        </div>
        <StatusBadge status={workflowCase.status} />
      </div>
      <div className="mt-3 flex items-center gap-3 text-xs text-neutral-400">
        <span>{format(new Date(workflowCase.created_at), "MMM d, yyyy HH:mm")}</span>
        {workflowCase.verdict && <StatusBadge status={workflowCase.verdict} />}
      </div>
    </div>
  );
}
