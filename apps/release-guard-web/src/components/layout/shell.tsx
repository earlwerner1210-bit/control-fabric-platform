"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

const NAV = [
  { href: "/dashboard",   label: "Dashboard",   icon: "◈" },
  { href: "/releases",    label: "Releases",    icon: "▶" },
  { href: "/approvals",   label: "Approvals",   icon: "✓" },
  { href: "/exceptions",  label: "Exceptions",  icon: "⚠" },
  { href: "/exports",     label: "Exports",     icon: "↓" },
  { href: "/settings",    label: "Settings",    icon: "⚙" },
];

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  return (
    <div className="min-h-screen flex bg-surface-raised">
      {/* Sidebar */}
      <aside className="w-56 bg-white border-r border-border flex flex-col shrink-0">
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-brand rounded-md flex items-center justify-center">
              <span className="text-white text-xs font-bold">RG</span>
            </div>
            <span className="font-semibold text-slate-800 text-sm">Release Guard</span>
          </div>
        </div>
        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5">
          {NAV.map(({ href, label, icon }) => {
            const active = path.startsWith(href);
            return (
              <Link key={href} href={href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                  active
                    ? "bg-brand/10 text-brand font-medium"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-800"
                )}>
                <span className="text-base w-4 text-center">{icon}</span>
                {label}
              </Link>
            );
          })}
        </nav>
        {/* Footer */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-xs font-semibold text-slate-600">
              U
            </div>
            <div>
              <div className="text-xs font-medium text-slate-700">My Workspace</div>
              <div className="text-[10px] text-slate-400">Starter plan</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-5xl mx-auto p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
