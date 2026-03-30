import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function severityColor(severity: string) {
  return (
    {
      critical: "text-red-400 bg-red-950/60 border-red-800",
      high: "text-orange-400 bg-orange-950/60 border-orange-800",
      medium: "text-yellow-400 bg-yellow-950/60 border-yellow-800",
      low: "text-emerald-400 bg-emerald-950/60 border-emerald-800",
    }[severity] ?? "text-zinc-400 bg-zinc-900 border-zinc-700"
  );
}

export function statusColor(status: string) {
  return (
    {
      open: "text-red-400 border-red-800",
      under_review: "text-yellow-400 border-yellow-800",
      resolved: "text-emerald-400 border-emerald-800",
      accepted_risk: "text-blue-400 border-blue-800",
    }[status] ?? "text-zinc-400 border-zinc-700"
  );
}

export function caseTypeColor(type: string) {
  return (
    {
      gap: "text-orange-300",
      conflict: "text-red-300",
      orphan: "text-yellow-300",
      duplicate: "text-blue-300",
    }[type] ?? "text-zinc-300"
  );
}

export function relativeTime(iso: string) {
  return formatDistanceToNow(new Date(iso), { addSuffix: true });
}

export function shortDate(iso: string) {
  return format(new Date(iso), "MMM d, HH:mm");
}

export function shortHash(hash: string) {
  return hash.slice(0, 12) + "...";
}
