import { cn } from "@/lib/utils";
export function Badge({ label, className }: { label: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border", className)}>
      {label}
    </span>
  );
}
