"use client";

import { useCallback, useState } from "react";
import { Upload } from "lucide-react";

interface FileUploadProps {
  onUpload: (file: File) => Promise<void>;
  accept?: string;
}

export default function FileUpload({ onUpload, accept = ".pdf,.doc,.docx,.txt,.csv" }: FileUploadProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setUploading(true);
      setFileName(file.name);
      try {
        await onUpload(file);
      } finally {
        setUploading(false);
        setFileName(null);
      }
    },
    [onUpload]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors ${
        dragging
          ? "border-blue-400 bg-blue-50"
          : "border-neutral-300 bg-neutral-50 hover:border-neutral-400"
      }`}
    >
      <Upload className="mb-3 h-8 w-8 text-neutral-400" />
      {uploading ? (
        <p className="text-sm text-neutral-600">
          Uploading <span className="font-medium">{fileName}</span>...
        </p>
      ) : (
        <>
          <p className="text-sm text-neutral-600">
            Drag and drop a file here, or{" "}
            <label className="cursor-pointer font-medium text-blue-600 hover:text-blue-500">
              browse
              <input
                type="file"
                className="sr-only"
                accept={accept}
                onChange={handleChange}
              />
            </label>
          </p>
          <p className="mt-1 text-xs text-neutral-400">
            PDF, DOC, DOCX, TXT, CSV
          </p>
        </>
      )}
    </div>
  );
}
