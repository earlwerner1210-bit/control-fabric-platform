"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview", icon: "◈" },
  { href: "/cases", label: "Case Queue", icon: "⚠" },
  { href: "/releases", label: "Release Gate", icon: "⊙" },
  { href: "/graph", label: "Graph Explorer", icon: "◎" },
  { href: "/objects", label: "Object Registry", icon: "▣" },
  { href: "/evidence", label: "Evidence Chain", icon: "⬡" },
  { href: "/exceptions", label: "Exceptions", icon: "⊘" },
  { href: "/rules", label: "Rules", icon: "≡" },
  { href: "/explain", label: "Explain", icon: "?" },
  { href: "/demo", label: "Demo Tenant", icon: "▷" },
  { href: "/journey", label: "Journey", icon: "→" },
  { href: "/reports", label: "Reports", icon: "📊" },
  { href: "/executive", label: "Executive", icon: "◈" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-52 bg-[#0d0f14] border-r border-[#1e2330] flex flex-col flex-shrink-0">
      <div className="px-4 py-5 border-b border-[#1e2330]">
        <div className="text-[10px] text-[#00e5b4] tracking-[0.2em] uppercase font-semibold">
          Control Fabric
        </div>
        <div className="text-[11px] text-slate-500 mt-0.5 tracking-wide">
          Operator Console
        </div>
      </div>
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded text-[12px] transition-all",
              path === item.href
                ? "bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430]"
                : "text-slate-500 hover:text-slate-300 hover:bg-[#ffffff08]"
            )}
          >
            <span className="text-[14px] w-4 text-center">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
      <div className="px-4 py-3 border-t border-[#1e2330]">
        <div className="text-[10px] text-slate-600">v1.0.0 · March 2026</div>
      </div>
    </aside>
  );
}
