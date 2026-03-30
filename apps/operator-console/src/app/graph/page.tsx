"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { shortHash } from "@/lib/utils";

export default function GraphPage() {
  const [objectId, setObjectId] = useState("");
  const [queried, setQueried] = useState("");

  const { data: traversal, isLoading: tLoading } = useQuery({
    queryKey: ["traversal", queried],
    queryFn: () => api.traverseGraph(queried),
    enabled: queried.length > 8,
  });
  const { data: impact, isLoading: iLoading } = useQuery({
    queryKey: ["impact", queried],
    queryFn: () => api.getImpact(queried),
    enabled: queried.length > 8,
  });
  const { data: obj } = useQuery({
    queryKey: ["object", queried],
    queryFn: () => api.getObject(queried),
    enabled: queried.length > 8,
  });

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-[15px] font-semibold text-slate-200">
          Graph Explorer
        </h1>
        <p className="text-[12px] text-slate-500 mt-0.5">
          Traverse the control graph and inspect impact chains
        </p>
      </div>

      <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4">
        <div className="flex gap-2">
          <input
            value={objectId}
            onChange={(e) => setObjectId(e.target.value)}
            placeholder="Paste control object ID..."
            className="flex-1 bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4]"
          />
          <button
            onClick={() => setQueried(objectId)}
            className="px-4 py-2 text-[12px] bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430] rounded hover:bg-[#00e5b425] transition-colors"
          >
            Explore
          </button>
        </div>
      </div>

      {obj && (
        <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 space-y-2">
          <div className="text-[11px] text-[#00e5b4] uppercase tracking-wider">
            Object
          </div>
          <div className="text-[14px] font-semibold text-slate-200">
            {obj.name}
          </div>
          <div className="grid grid-cols-3 gap-4 mt-2">
            {(
              [
                ["Type", obj.object_type],
                ["State", obj.state],
                ["Plane", obj.operational_plane],
                ["Version", `v${obj.version}`],
                ["Schema", obj.schema_namespace],
                ["Hash", shortHash(obj.object_hash)],
              ] as const
            ).map(([k, v]) => (
              <div key={k}>
                <div className="text-[10px] text-slate-600">{k}</div>
                <div className="text-[12px] text-slate-300 font-mono">{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {(tLoading || iLoading) && (
        <div className="text-[12px] text-slate-500 text-center py-8">
          Traversing graph...
        </div>
      )}

      {traversal && impact && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 space-y-3">
            <div className="text-[11px] text-slate-500 uppercase tracking-wider">
              Traversal
            </div>
            <div className="grid grid-cols-2 gap-3">
              {(
                [
                  [
                    "Discovered objects",
                    traversal.discovered_objects.length,
                  ],
                  ["Discovered edges", traversal.discovered_edges.length],
                  ["Depth reached", traversal.depth_reached],
                  ["Paths found", traversal.path_count],
                ] as const
              ).map(([k, v]) => (
                <div key={k}>
                  <div className="text-[10px] text-slate-600">{k}</div>
                  <div className="text-[16px] font-semibold text-slate-300">
                    {v}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-4 space-y-3">
            <div className="text-[11px] text-slate-500 uppercase tracking-wider">
              Impact analysis
            </div>
            <div className="grid grid-cols-2 gap-3">
              {(
                [
                  ["Downstream", impact.downstream_objects.length],
                  ["Upstream", impact.upstream_objects.length],
                  ["Total affected", impact.total_affected_objects],
                  [
                    "Critical relationships",
                    impact.critical_relationships.length,
                  ],
                ] as const
              ).map(([k, v]) => (
                <div key={k}>
                  <div className="text-[10px] text-slate-600">{k}</div>
                  <div
                    className={`text-[16px] font-semibold ${Number(v) > 0 && k.includes("Critical") ? "text-orange-400" : "text-slate-300"}`}
                  >
                    {v}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {impact.critical_relationships.length > 0 && (
            <div className="col-span-2 bg-[#111318] border border-orange-900/40 rounded-lg p-4">
              <div className="text-[11px] text-orange-400 uppercase tracking-wider mb-3">
                Critical relationships
              </div>
              <div className="space-y-2">
                {impact.critical_relationships.map((r) => (
                  <div
                    key={r.edge_id}
                    className="flex items-center gap-3 text-[11px] font-mono"
                  >
                    <span className="text-slate-600">
                      {shortHash(r.source)}
                    </span>
                    <span className="text-orange-400">—[{r.type}]→</span>
                    <span className="text-slate-600">
                      {shortHash(r.target)}
                    </span>
                    <span className="text-slate-500 ml-auto">
                      weight: {r.enforcement_weight}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
