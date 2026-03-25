"use client";

import { useState, useMemo } from "react";

interface PromptEditorProps {
  value: string;
  variables: string[];
  onChange: (value: string) => void;
  disabled?: boolean;
}

export default function PromptEditor({ value, variables, onChange, disabled = false }: PromptEditorProps) {
  const variableSet = useMemo(() => new Set(variables), [variables]);

  // Highlight variable patterns like {{variable_name}} in the display
  const highlightedParts = useMemo(() => {
    const pattern = /(\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\})/g;
    const parts = value.split(pattern);
    return parts.map((part, idx) => {
      const match = part.match(/^\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}$/);
      if (match) {
        const varName = match[1];
        const isKnown = variableSet.has(varName);
        return (
          <span
            key={idx}
            className={`rounded px-0.5 ${
              isKnown
                ? "bg-blue-100 text-blue-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {part}
          </span>
        );
      }
      return <span key={idx}>{part}</span>;
    });
  }, [value, variableSet]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {variables.map((v) => (
          <span
            key={v}
            className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700"
          >
            {`{{${v}}}`}
          </span>
        ))}
      </div>
      <div className="relative">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          rows={16}
          className="block w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 font-mono text-sm text-neutral-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-neutral-50 disabled:text-neutral-500"
          spellCheck={false}
        />
      </div>
      {/* Preview with highlighted variables */}
      <details>
        <summary className="cursor-pointer text-xs font-medium text-neutral-500 hover:text-neutral-700">
          Preview with variable highlighting
        </summary>
        <div className="mt-2 rounded-lg border border-neutral-200 bg-neutral-50 p-3 text-sm font-mono whitespace-pre-wrap">
          {highlightedParts}
        </div>
      </details>
    </div>
  );
}
