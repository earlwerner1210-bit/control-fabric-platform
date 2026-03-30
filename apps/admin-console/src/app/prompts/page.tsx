"use client";

import { useEffect, useState, useCallback } from "react";
import { listPromptTemplates, updatePromptTemplate } from "@/lib/api";
import type { PromptTemplate } from "@/lib/types";
import PromptEditor from "@/components/PromptEditor";

export default function PromptsPage() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [selected, setSelected] = useState<PromptTemplate | null>(null);
  const [editValue, setEditValue] = useState("");
  const [originalValue, setOriginalValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listPromptTemplates();
      setTemplates(data);
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const handleSelect = (t: PromptTemplate) => {
    setSelected(t);
    setEditValue(t.template);
    setOriginalValue(t.template);
    setMessage(null);
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    setMessage(null);
    try {
      const updated = await updatePromptTemplate(selected.id, { template: editValue });
      setSelected(updated);
      setOriginalValue(updated.template);
      setTemplates((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      setMessage({ type: "success", text: "Template saved successfully." });
    } catch (err: any) {
      setMessage({ type: "error", text: err?.response?.data?.detail ?? "Failed to save." });
    } finally {
      setSaving(false);
    }
  };

  const handleRevert = () => {
    setEditValue(originalValue);
    setMessage(null);
  };

  const isDirty = editValue !== originalValue;

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Prompt Templates</h1>
      <p className="mt-1 text-sm text-neutral-500">Manage prompt templates used across workflows.</p>

      <div className="mt-6 grid grid-cols-12 gap-6">
        {/* Template list */}
        <div className="col-span-4">
          <div className="rounded-lg border border-neutral-200 bg-white">
            <div className="border-b border-neutral-200 px-4 py-3">
              <h3 className="text-sm font-medium text-neutral-700">Templates</h3>
            </div>
            {loading ? (
              <p className="px-4 py-6 text-sm text-neutral-400">Loading...</p>
            ) : templates.length === 0 ? (
              <p className="px-4 py-6 text-sm text-neutral-400">No templates found.</p>
            ) : (
              <ul className="divide-y divide-neutral-200">
                {templates.map((t) => (
                  <li key={t.id}>
                    <button
                      onClick={() => handleSelect(t)}
                      className={`w-full px-4 py-3 text-left transition-colors ${
                        selected?.id === t.id
                          ? "bg-blue-50"
                          : "hover:bg-neutral-50"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-neutral-900">{t.name}</p>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                            t.is_active
                              ? "bg-green-100 text-green-700"
                              : "bg-neutral-100 text-neutral-500"
                          }`}
                        >
                          {t.is_active ? "active" : "inactive"}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs text-neutral-500">{t.domain_pack} - v{t.version}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Editor */}
        <div className="col-span-8">
          {selected ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-medium text-neutral-900">{selected.name}</h3>
                  <p className="text-sm text-neutral-500">{selected.description}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleRevert}
                    disabled={!isDirty}
                    className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Revert
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={!isDirty || saving}
                    className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                </div>
              </div>

              {message && (
                <div
                  className={`rounded-md border px-3 py-2 text-sm ${
                    message.type === "success"
                      ? "border-green-200 bg-green-50 text-green-700"
                      : "border-red-200 bg-red-50 text-red-700"
                  }`}
                >
                  {message.text}
                </div>
              )}

              <PromptEditor
                value={editValue}
                variables={selected.variables}
                onChange={setEditValue}
              />
            </div>
          ) : (
            <div className="flex h-64 items-center justify-center rounded-lg border border-neutral-200 bg-white">
              <p className="text-sm text-neutral-400">Select a template to edit</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
