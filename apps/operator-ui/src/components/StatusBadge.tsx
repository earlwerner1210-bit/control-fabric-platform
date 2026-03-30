interface StatusBadgeProps {
  status: string;
  className?: string;
}

const colorMap: Record<string, string> = {
  // workflow statuses
  pending: "bg-neutral-100 text-neutral-700",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-neutral-100 text-neutral-500",
  // validation statuses
  passed: "bg-green-100 text-green-700",
  warned: "bg-yellow-100 text-yellow-700",
  blocked: "bg-red-100 text-red-700",
  escalated: "bg-purple-100 text-purple-700",
  // verdicts
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  needs_review: "bg-yellow-100 text-yellow-700",
  ready: "bg-green-100 text-green-700",
  warn: "bg-yellow-100 text-yellow-700",
  escalate: "bg-purple-100 text-purple-700",
  billable: "bg-green-100 text-green-700",
  non_billable: "bg-neutral-100 text-neutral-700",
  under_recovery: "bg-yellow-100 text-yellow-700",
  penalty_risk: "bg-red-100 text-red-700",
  unknown: "bg-neutral-100 text-neutral-500",
};

export default function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const colors = colorMap[status] ?? "bg-neutral-100 text-neutral-600";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colors} ${className}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
