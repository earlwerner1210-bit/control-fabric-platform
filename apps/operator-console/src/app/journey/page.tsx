"use client";

import { useState } from "react";
import { api, JourneyStep } from "@/lib/api";

export default function JourneyPage() {
  const [steps, setSteps] = useState<JourneyStep[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [stepResults, setStepResults] = useState<Record<number, any>>({});
  const [loading, setLoading] = useState(false);
  const [orgName, setOrgName] = useState("Demo Corp");
  const [userName, setUserName] = useState("operator@demo.com");

  async function loadSteps() {
    const data = await api.getJourneySteps();
    setSteps(data.steps);
  }

  async function startJourney() {
    setLoading(true);
    try {
      const r = await api.startJourney(orgName, userName);
      setSessionId(r.session_id);
      setCurrentStep(1);
      setStepResults({ 1: r });
    } finally {
      setLoading(false);
    }
  }

  async function runStep(step: number) {
    if (!sessionId) return;
    setLoading(true);
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let result: any;
      switch (step) {
        case 2:
          result = await api.journeyConnectSource(sessionId, "github-ci", "ci_pipeline");
          break;
        case 3:
          result = await api.journeyInstallPack(sessionId);
          break;
        case 4:
          result = await api.journeyApplyDefaults(sessionId);
          break;
        case 5:
          result = await api.journeyIngestSample(sessionId);
          break;
        case 6:
          result = await api.journeyReconcile(sessionId);
          break;
        case 7:
          result = await api.journeyEvidenceSummary(sessionId);
          break;
        case 8:
          result = await api.journeyDemonstrateGate(sessionId);
          break;
        case 9:
          result = await api.journeyAuditReport(sessionId);
          break;
        default:
          result = {};
      }
      setStepResults((prev) => ({ ...prev, [step]: result }));
      setCurrentStep(step);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-lg font-semibold text-slate-200">Golden-Path Journey</h1>
      <p className="text-sm text-slate-500">
        Step-by-step onboarding wizard — set up governance from scratch.
      </p>

      {steps.length === 0 && (
        <button
          onClick={loadSteps}
          className="px-4 py-2 bg-[#0d0f14] border border-[#1e2330] rounded text-sm text-slate-400 hover:text-slate-200"
        >
          Load Journey
        </button>
      )}

      {steps.length > 0 && !sessionId && (
        <div className="p-4 bg-[#0d0f14] border border-[#1e2330] rounded space-y-3">
          <div className="text-xs text-slate-500 uppercase tracking-wider">Start Your Journey</div>
          <div className="flex gap-2">
            <input
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="Organisation name"
              className="flex-1 px-3 py-2 bg-[#0a0c10] border border-[#1e2330] rounded text-sm text-slate-300"
            />
            <input
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              placeholder="Your email"
              className="flex-1 px-3 py-2 bg-[#0a0c10] border border-[#1e2330] rounded text-sm text-slate-300"
            />
          </div>
          <button
            onClick={startJourney}
            disabled={loading}
            className="px-4 py-2 bg-[#00e5b4] text-[#0d0f14] text-sm font-medium rounded hover:bg-[#00c9a0] disabled:opacity-50"
          >
            {loading ? "Starting…" : "Begin Journey"}
          </button>
        </div>
      )}

      {steps.length > 0 && (
        <div className="space-y-2">
          {steps.map((s) => {
            const isDone = stepResults[s.step] !== undefined;
            const isCurrent = s.step === currentStep + 1;
            const isLocked = s.step > currentStep + 1;
            return (
              <div
                key={s.step}
                className={`p-3 border rounded flex items-center justify-between ${
                  isDone
                    ? "bg-[#00e5b408] border-[#00e5b420]"
                    : isCurrent
                      ? "bg-[#0d0f14] border-[#00e5b440]"
                      : "bg-[#0d0f14] border-[#1e2330]"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      isDone
                        ? "bg-[#00e5b4] text-[#0d0f14]"
                        : "bg-[#1e2330] text-slate-500"
                    }`}
                  >
                    {isDone ? "✓" : s.step}
                  </span>
                  <div>
                    <div className="text-xs text-slate-300">{s.name}</div>
                    <div className="text-[10px] text-slate-600">{s.description}</div>
                  </div>
                </div>
                {isCurrent && sessionId && (
                  <button
                    onClick={() => runStep(s.step)}
                    disabled={loading}
                    className="px-3 py-1 text-[10px] bg-[#00e5b4] text-[#0d0f14] font-medium rounded hover:bg-[#00c9a0] disabled:opacity-50"
                  >
                    {loading ? "…" : "Run"}
                  </button>
                )}
                {isLocked && (
                  <span className="text-[10px] text-slate-600">Locked</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {Object.keys(stepResults).length > 0 && (
        <div className="p-4 bg-[#0d0f14] border border-[#1e2330] rounded">
          <div className="text-xs text-slate-500 mb-2 uppercase tracking-wider">
            Step {currentStep} Result
          </div>
          <pre className="text-[10px] text-slate-400 overflow-x-auto">
            {JSON.stringify(stepResults[currentStep], null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
