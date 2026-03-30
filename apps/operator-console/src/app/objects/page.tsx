"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { shortHash, shortDate, relativeTime } from "@/lib/utils";

export default function ObjectsPage() {
  const [objectId, setObjectId] = useState("");
  const [queried, setQueried] = useState("");
  const { data: obj } = useQuery({
    queryKey: ["object", queried],
    queryFn: () => api.getObject(queried),
    enabled: queried.length > 8,
  });
  const { data: history } = useQuery({
    queryKey: ["history", queried],
    queryFn: () => api.getObjectHistory(queried),
    enabled: queried.length > 8,
  });

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <h1 className="text-[15px] font-semibold text-slate-200">
          Object Registry
        </h1>
        <p className="text-[12px] text-slate-500 mt-0.5">
          Inspect control objects and their immutable version history
        </p>
      </div>

      <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4">
        <div className="flex gap-2">
          <input
            value={objectId}
            onChange={(e) => setObjectId(e.target.value)}
            placeholder="Paste object ID..."
            className="flex-1 bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4]"
          />
          <button
            onClick={() => setQueried(objectId)}
            className="px-4 py-2 text-[12px] bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430] rounded hover:bg-[#00e5b425] transition-colors"
          >
            Look up
          </button>
        </div>
      </div>

      {obj && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 space-y-4">
          <div>
            <div className="text-[11px] text-[#00e5b4] uppercase tracking-wider">
              Control Object
            </div>
            <div className="text-[15px] font-semibold text-slate-200 mt-1">
              {obj.name}
            </div>
            {obj.description && (
              <div className="text-[12px] text-slate-500 mt-1">
                {obj.description}
              </div>
            )}
          </div>
          <div className="grid grid-cols-3 gap-4">
            {(
              [
                ["Object type", obj.object_type],
                ["State", obj.state],
                ["Version", `v${obj.version}`],
                ["Plane", obj.operational_plane],
                ["Schema", obj.schema_namespace],
                ["Created", shortDate(obj.created_at)],
              ] as const
            ).map(([k, v]) => (
              <div key={k}>
                <div className="text-[10px] text-slate-600">{k}</div>
                <div className="text-[12px] text-slate-300">{v}</div>
              </div>
            ))}
          </div>
          <div className="pt-2 border-t border-[#1e2330] space-y-1">
            <div className="text-[10px] text-slate-600 uppercase tracking-wider">
              Provenance
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-[10px] text-slate-600">Source system</div>
                <div className="text-[12px] text-slate-300">
                  {obj.provenance.source_system}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-600">Ingested by</div>
                <div className="text-[12px] text-slate-300">
                  {obj.provenance.ingested_by}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-600">Ingested at</div>
                <div className="text-[12px] text-slate-300">
                  {shortDate(obj.provenance.ingested_at)}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-600">Source hash</div>
                <div className="hash">
                  {shortHash(obj.provenance.source_hash)}
                </div>
              </div>
            </div>
          </div>
          <div className="hash">
            <span className="text-slate-600">object_hash: </span>
            {obj.object_hash}
          </div>
        </div>
      )}

      {history && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 space-y-3">
          <div className="text-[11px] text-slate-500 uppercase tracking-wider">
            Version history — {history.version_count} records — append-only
          </div>
          <div className="space-y-2">
            {history.history.map((h) => (
              <div
                key={h.record_hash}
                className="flex items-start gap-3 py-2 border-b border-[#1e2330] last:border-0"
              >
                <span className="text-[11px] font-mono text-[#00e5b4] w-6 flex-shrink-0">
                  v{h.version}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] uppercase px-1.5 py-0.5 rounded border ${
                        h.state === "active"
                          ? "text-emerald-400 border-emerald-900/60"
                          : h.state === "deprecated"
                            ? "text-slate-500 border-[#1e2330]"
                            : "text-slate-400 border-[#1e2330]"
                      }`}
                    >
                      {h.state}
                    </span>
                    <span className="text-[11px] text-slate-500">
                      {h.change_reason}
                    </span>
                  </div>
                  <div className="hash mt-0.5">
                    {shortHash(h.record_hash)}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-[11px] text-slate-500">
                    {h.changed_by}
                  </div>
                  <div className="text-[10px] text-slate-600">
                    {relativeTime(h.recorded_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
