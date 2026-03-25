"use client";

import { useEffect, useState, useCallback } from "react";
import { format } from "date-fns";
import { uploadDocument, listDocuments, parseDocument, embedDocument } from "@/lib/api";
import type { Document, PaginatedResponse } from "@/lib/types";
import FileUpload from "@/components/FileUpload";
import DataTable, { type Column } from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  const loadDocs = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const res = await listDocuments(p);
      setDocs(res.items);
      setTotalPages(res.total_pages);
      setPage(res.page);
    } catch {
      // API not yet available
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocs(1);
  }, [loadDocs]);

  const handleUpload = async (file: File) => {
    await uploadDocument(file);
    await loadDocs(page);
  };

  const handleParse = async (id: string) => {
    setActionLoading((prev) => ({ ...prev, [`parse-${id}`]: true }));
    try {
      await parseDocument(id);
      await loadDocs(page);
    } finally {
      setActionLoading((prev) => ({ ...prev, [`parse-${id}`]: false }));
    }
  };

  const handleEmbed = async (id: string) => {
    setActionLoading((prev) => ({ ...prev, [`embed-${id}`]: true }));
    try {
      await embedDocument(id);
      await loadDocs(page);
    } finally {
      setActionLoading((prev) => ({ ...prev, [`embed-${id}`]: false }));
    }
  };

  const columns: Column<Document>[] = [
    { header: "Filename", accessor: (row) => <span className="font-medium">{row.filename}</span> },
    { header: "Type", accessor: "content_type" },
    { header: "Status", accessor: (row) => <StatusBadge status={row.status} /> },
    {
      header: "Size",
      accessor: (row) => {
        const kb = row.size_bytes / 1024;
        return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`;
      },
    },
    {
      header: "Created",
      accessor: (row) => format(new Date(row.created_at), "MMM d, yyyy HH:mm"),
    },
    {
      header: "Actions",
      accessor: (row) => (
        <div className="flex gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleParse(row.id);
            }}
            disabled={actionLoading[`parse-${row.id}`]}
            className="rounded border border-neutral-300 px-2 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40"
          >
            {actionLoading[`parse-${row.id}`] ? "Parsing..." : "Parse"}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleEmbed(row.id);
            }}
            disabled={actionLoading[`embed-${row.id}`]}
            className="rounded border border-neutral-300 px-2 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40"
          >
            {actionLoading[`embed-${row.id}`] ? "Embedding..." : "Embed"}
          </button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Documents</h1>
      <p className="mt-1 text-sm text-neutral-500">Upload, parse, and embed documents for processing.</p>

      <div className="mt-6">
        <FileUpload onUpload={handleUpload} />
      </div>

      <div className="mt-6">
        {loading ? (
          <p className="text-sm text-neutral-400">Loading documents...</p>
        ) : (
          <DataTable
            columns={columns}
            data={docs}
            page={page}
            totalPages={totalPages}
            onPageChange={loadDocs}
            emptyMessage="No documents uploaded yet."
          />
        )}
      </div>
    </div>
  );
}
