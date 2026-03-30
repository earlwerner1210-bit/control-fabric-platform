"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/utils";

export default function ExceptionsPage() {
  const { data } = useQuery({
    queryKey: ["exceptions"],
    queryFn: api.getActiveExceptions,
    refetchInterval: 30_000,
  });

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <h1 className="text-[15px] font-semibold text-slate-200">
          Active Exceptions
        </h1>
        <p className="text-[12px] text-slate-500 mt-0.5">
          All time-bound exceptions — none are permanent
        </p>
      </div>

      {data?.count === 0 && (
        <div className="bg-[#0a1a12] border border-emerald-900/40 rounded-lg p-6 text-center">
          <div className="text-[12px] text-emerald-400">
            No active exceptions
          </div>
          <div className="text-[11px] text-slate-600 mt-1">
            Platform operating under standard governance
          </div>
        </div>
      )}

      <div className="space-y-3">
        {data?.exceptions.map((e) => (
          <div
            key={e.exception_id}
            className="bg-[#111318] border border-yellow-900/40 rounded-lg p-4 space-y-2"
          >
            <div className="flex items-center justify-between">
              <span
                className={`text-[11px] uppercase font-semibold px-2 py-0.5 rounded border ${
                  e.risk === "critical"
                    ? "text-red-400 border-red-900/60 bg-red-950/40"
                    : "text-yellow-400 border-yellow-900/60 bg-yellow-950/40"
                }`}
              >
                {e.risk}
              </span>
              <span className="text-[11px] text-slate-600">
                expires {relativeTime(e.expires_at)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-[10px] text-slate-600">
                  Exception type
                </div>
                <div className="text-[12px] text-slate-300">{e.type}</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-600">Requested by</div>
                <div className="text-[12px] text-slate-300">
                  {e.requested_by}
                </div>
              </div>
              <div className="col-span-2">
                <div className="text-[10px] text-slate-600">Exception ID</div>
                <div className="hash">{e.exception_id}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
