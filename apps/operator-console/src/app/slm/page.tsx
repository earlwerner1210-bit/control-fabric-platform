"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

const DOMAINS = [
  "telecom", "legal", "healthcare", "banking",
  "insurance", "finserv", "manufacturing", "semiconductor",
];

const GRADE_COLOR: Record<string, string> = {
  A: "text-emerald-400", B: "text-emerald-300",
  C: "text-yellow-400",  D: "text-orange-400", F: "text-red-400",
};

export default function SLMPage() {
  const [selected, setSelected] = useState("telecom");

  const { data: adapters } = useQuery({
    queryKey: ["slm-adapters"],
    queryFn: () => fetch(`${process.env.NEXT_PUBLIC_API_URL}/slm/adapters`).then(r => r.json()),
  });

  const { data: routeTest } = useQuery({
    queryKey: ["slm-route", selected],
    queryFn: () => fetch(`${process.env.NEXT_PUBLIC_API_URL}/slm/route?operational_plane=operations&object_type=regulatory_mandate`).then(r => r.json()),
    enabled: !!selected,
  });

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-[15px] font-semibold text-slate-200">Domain SLM Status</h1>
        <p className="text-[12px] text-slate-500 mt-0.5">Fine-tuned model status, regulatory coverage, and enrichment quality per domain</p>
      </div>

      {/* Adapter registry */}
      <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5">
        <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-4">
          Registered domain adapters — {adapters?.adapter_count ?? 0} loaded
        </div>
        <div className="grid grid-cols-2 gap-3">
          {(adapters?.adapters ?? []).map((a: any) => (
            <div key={a.adapter_id}
              onClick={() => setSelected(a.domain)}
              className={cn("border rounded-lg p-3 cursor-pointer transition-all",
                selected === a.domain
                  ? "border-[#00e5b430] bg-[#00e5b408]"
                  : "border-[#1e2330] hover:bg-[#ffffff03]")}>
              <div className="flex justify-between items-start">
                <div className="text-[12px] font-semibold text-slate-200 capitalize">{a.domain?.replace("_", " ")}</div>
                <span className="text-[9px] px-2 py-0.5 rounded bg-[#1e2330] text-slate-500 font-mono">{a.adapter_id}</span>
              </div>
              <div className="text-[10px] text-slate-600 mt-1">
                Planes: {(a.planes ?? []).join(", ") || "all"}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Training status */}
      <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5">
        <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-4">Training status</div>
        <div className="space-y-2">
          {DOMAINS.map(domain => {
            const isComplete = domain === "telecom";
            return (
              <div key={domain} className="flex items-center gap-3">
                <div className="w-28 text-[11px] capitalize text-slate-400">{domain}</div>
                <div className="flex-1 h-1.5 bg-[#1e2330] rounded-full overflow-hidden">
                  <div className={cn("h-full rounded-full", isComplete ? "bg-emerald-400" : "bg-[#7C3AED]")}
                    style={{ width: isComplete ? "100%" : "30%" }} />
                </div>
                <div className={cn("text-[10px] w-32 text-right", isComplete ? "text-emerald-400" : "text-[#A78BFA]")}>
                  {isComplete ? "Fine-tuned" : "Manus training"}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Test enrichment */}
      <EnrichmentTester />
    </div>
  );
}

function EnrichmentTester() {
  const [hypothesis, setHypothesis] = useState("");
  const [plane, setPlane] = useState("operations");
  const [regCtx, setRegCtx] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const test = async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/slm/enrich`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hypothesis_text: hypothesis,
          operational_plane: plane,
          regulatory_context: regCtx ? regCtx.split(",").map(s => s.trim()) : [],
        }),
      });
      setResult(await resp.json());
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-[#111318] border border-[#1e2330] rounded-lg p-5 space-y-4">
      <div className="text-[10px] text-slate-500 uppercase tracking-wider">Test domain enrichment</div>
      <div className="grid grid-cols-2 gap-3">
        <input value={plane} onChange={e => setPlane(e.target.value)} placeholder="Plane (e.g. operations)"
          className="bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4]" />
        <input value={regCtx} onChange={e => setRegCtx(e.target.value)} placeholder="Regulatory context (e.g. NIS2, SRA)"
          className="bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4]" />
      </div>
      <textarea value={hypothesis} onChange={e => setHypothesis(e.target.value)}
        placeholder="Enter a governance hypothesis or finding to enrich..."
        rows={3}
        className="w-full bg-[#0a0c10] border border-[#252d3d] rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00e5b4] resize-none" />
      <button onClick={test} disabled={!hypothesis || loading}
        className="text-[11px] px-4 py-2 bg-[#00e5b415] text-[#00e5b4] border border-[#00e5b430] rounded disabled:opacity-40">
        {loading ? "Enriching..." : "Test enrichment"}
      </button>

      {result && (
        <div className="space-y-3 pt-2 border-t border-[#1e2330]">
          <div className="flex gap-4 text-[11px]">
            <span className="text-slate-500">Adapter: <span className="text-slate-300">{result.adapter_used}</span></span>
            <span className="text-slate-500">Domain: <span className="text-slate-300">{result.domain}</span></span>
            <span className={cn("ml-auto", result.enriched ? "text-emerald-400" : "text-slate-500")}>
              {result.enriched ? "Enriched" : "No enrichment (fallback)"}
            </span>
          </div>
          {result.regulation_citations?.length > 0 && (
            <div>
              <div className="text-[10px] text-slate-600 mb-1">Regulation citations</div>
              {result.regulation_citations.map((c: string, i: number) => (
                <div key={i} className="text-[11px] text-[#00e5b4] border-l-2 border-[#00e5b430] pl-2 mb-1">{c}</div>
              ))}
            </div>
          )}
          {result.remediation_precision && (
            <div>
              <div className="text-[10px] text-slate-600 mb-1">Remediation</div>
              <div className="text-[11px] text-slate-400">{result.remediation_precision}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
