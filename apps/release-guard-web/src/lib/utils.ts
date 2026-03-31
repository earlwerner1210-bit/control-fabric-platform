import { clsx, type ClassValue } from "clsx";
export function cn(...inputs: ClassValue[]) { return clsx(inputs); }

export const STATUS_COLORS: Record<string, string> = {
  approved: "text-green-700 bg-green-50 border-green-200",
  blocked:  "text-red-700 bg-red-50 border-red-200",
  pending:  "text-amber-700 bg-amber-50 border-amber-200",
  draft:    "text-slate-600 bg-slate-50 border-slate-200",
  cancelled: "text-slate-400 bg-slate-50 border-slate-200",
  released: "text-blue-700 bg-blue-50 border-blue-200",
};

export const RISK_COLORS: Record<string, string> = {
  low:      "text-green-700 bg-green-50 border-green-200",
  medium:   "text-amber-700 bg-amber-50 border-amber-200",
  high:     "text-orange-700 bg-orange-50 border-orange-200",
  critical: "text-red-700 bg-red-50 border-red-200",
};

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 2) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function initials(name: string): string {
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
}
