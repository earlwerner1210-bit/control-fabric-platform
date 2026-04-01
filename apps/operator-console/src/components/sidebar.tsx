"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

// All 18 screens
const ALL_NAV = [
  { href: "/",               label: "Overview",        icon: "◈" },
  { href: "/cases",          label: "Cases",           icon: "⚠" },
  { href: "/release-gate",   label: "Release Gate",    icon: "▶" },
  { href: "/graph",          label: "Graph Explorer",  icon: "⬡" },
  { href: "/registry",       label: "Object Registry", icon: "☰" },
  { href: "/evidence",       label: "Evidence Chain",  icon: "⬜" },
  { href: "/exceptions",     label: "Exceptions",      icon: "⛔" },
  { href: "/rules",          label: "Rules",           icon: "≡" },
  { href: "/explain",        label: "Explainability",  icon: "?" },
  { href: "/compliance",     label: "Compliance",      icon: "✓" },
  { href: "/analytics",      label: "Analytics",       icon: "↗" },
  { href: "/executive",      label: "Executive",       icon: "◇" },
  { href: "/slm",            label: "SLM Status",      icon: "◈" },
  { href: "/readiness",      label: "Readiness",       icon: "⬡" },
  { href: "/infrastructure", label: "Infrastructure",  icon: "⬡" },
  { href: "/journey",        label: "Journey",         icon: "→" },
  { href: "/reports",        label: "Reports",         icon: "↓" },
  { href: "/demo",           label: "Demo Tenant",     icon: "▷" },
];

// Pilot mode: 5 screens that matter for the buyer conversation
const PILOT_NAV = [
  { href: "/",             label: "Overview",     icon: "◈" },
  { href: "/cases",        label: "Cases",        icon: "⚠" },
  { href: "/release-gate", label: "Release Gate", icon: "▶" },
  { href: "/compliance",   label: "Compliance",   icon: "✓" },
  { href: "/executive",    label: "Executive",    icon: "◇" },
];

const PILOT_MODE = process.env.NEXT_PUBLIC_PILOT_MODE === "true";

export function Sidebar() {
  const pathname = usePathname();
  const nav = PILOT_MODE ? PILOT_NAV : ALL_NAV;

  return (
    <aside className="flex flex-col w-52 min-h-screen bg-[#0a0c10] border-r border-[#1e2330] shrink-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-[#1e2330]">
        <div className="text-[13px] font-bold text-slate-200 tracking-tight">
          Control Fabric
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">
          {PILOT_MODE ? "Pilot" : "Platform"}
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {nav.map(({ href, label, icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link key={href} href={href}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-lg text-[12px] transition-colors",
                active
                  ? "bg-[#00e5b415] text-[#00e5b4] font-medium"
                  : "text-slate-500 hover:text-slate-300 hover:bg-[#ffffff06]"
              )}>
              <span className="text-[11px] w-4 text-center flex-shrink-0">{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Pilot badge */}
      {PILOT_MODE && (
        <div className="px-4 py-3 border-t border-[#1e2330]">
          <div className="text-[9px] text-amber-500 font-semibold uppercase tracking-wider">
            Pilot mode
          </div>
          <div className="text-[9px] text-slate-600 mt-0.5">
            Set NEXT_PUBLIC_PILOT_MODE=false to see all screens
          </div>
        </div>
      )}

      {/* Version */}
      <div className="px-4 py-3 border-t border-[#1e2330]">
        <div className="text-[9px] text-slate-600">v1.0.0 · Control Fabric</div>
      </div>
    </aside>
  );
}
