"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { listDomainPackVersions } from "@/lib/api";
import type { DomainPackVersion } from "@/lib/types";
import DataTable, { type Column } from "@/components/DataTable";

export default function DomainPacksPage() {
  const [packs, setPacks] = useState<DomainPackVersion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await listDomainPackVersions();
        setPacks(data);
      } catch {
        // API not available
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const columns: Column<DomainPackVersion>[] = [
    {
      header: "Pack Name",
      accessor: (row) => <span className="font-medium">{row.pack_name}</span>,
    },
    { header: "Version", accessor: "version" },
    {
      header: "Status",
      accessor: (row) => (
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
            row.is_active
              ? "bg-green-100 text-green-700"
              : "bg-neutral-100 text-neutral-500"
          }`}
        >
          {row.is_active ? "active" : "inactive"}
        </span>
      ),
    },
    { header: "Prompts", accessor: (row) => row.prompt_count },
    { header: "Rules", accessor: (row) => row.rule_count },
    { header: "Schemas", accessor: (row) => row.schema_count },
    {
      header: "Published",
      accessor: (row) => format(new Date(row.published_at), "MMM d, yyyy"),
    },
    {
      header: "Description",
      accessor: (row) => (
        <span className="max-w-xs truncate text-neutral-500">{row.description}</span>
      ),
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Domain Packs</h1>
      <p className="mt-1 text-sm text-neutral-500">
        View domain pack versions with their prompts, rules, and schemas.
      </p>

      <div className="mt-6">
        {loading ? (
          <p className="text-sm text-neutral-400">Loading domain packs...</p>
        ) : (
          <DataTable
            columns={columns}
            data={packs}
            emptyMessage="No domain pack versions found."
          />
        )}
      </div>
    </div>
  );
}
