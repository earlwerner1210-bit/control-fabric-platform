"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquareText, Package, Activity, FlaskConical } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Activity },
  { href: "/prompts", label: "Prompts", icon: MessageSquareText },
  { href: "/domain-packs", label: "Domain Packs", icon: Package },
  { href: "/model-runs", label: "Model Runs", icon: Activity },
  { href: "/evals", label: "Evals", icon: FlaskConical },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 w-60 border-r border-neutral-200 bg-white flex flex-col">
      <div className="flex h-14 items-center border-b border-neutral-200 px-5">
        <span className="text-lg font-semibold text-neutral-900">Admin Console</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-neutral-100 text-neutral-900"
                  : "text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900"
              }`}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-neutral-200 px-5 py-3">
        <p className="text-xs text-neutral-400">Admin Console v0.1</p>
      </div>
    </aside>
  );
}
