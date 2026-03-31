"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STEPS = [
  { id: "welcome",        label: "Welcome",            number: 1 },
  { id: "connect_github", label: "Connect GitHub",     number: 2 },
  { id: "connect_jira",   label: "Connect Jira",       number: 3 },
  { id: "select_profile", label: "Choose rules",       number: 4 },
  { id: "invite_approver", label: "Invite approver",   number: 5 },
  { id: "run_demo",       label: "See it in action",   number: 6 },
];

const PROFILES = [
  { id: "startup_default", label: "Startup", desc: "Jira ticket + CI pass. One approver for high-risk." },
  { id: "regulated_default", label: "Regulated", desc: "Adds security scan. Approvals for medium risk and above." },
  { id: "strict", label: "Strict", desc: "All checks. Two approvers for critical releases." },
];

export default function OnboardingPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [workspaceId, setWorkspaceId] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [jiraUrl, setJiraUrl] = useState("");
  const [jiraEmail, setJiraEmail] = useState("");
  const [jiraToken, setJiraToken] = useState("");
  const [selectedProfile, setSelectedProfile] = useState("startup_default");
  const [approverEmail, setApproverEmail] = useState("");

  const createWorkspace = useMutation({
    mutationFn: () => api.createWorkspace(workspaceName),
    onSuccess: async (data: any) => {
      setWorkspaceId(data.workspace_id);
      await api.startOnboarding(data.workspace_id);
      setStep(1);
    },
  });

  const connectGitHub = useMutation({
    mutationFn: () => api.connectGitHub(workspaceId, { token: githubToken }),
    onSuccess: () => setStep(2),
  });

  const connectJira = useMutation({
    mutationFn: () => api.connectJira(workspaceId, { base_url: jiraUrl, email: jiraEmail, token: jiraToken }),
    onSuccess: () => setStep(3),
  });

  const loadDefaults = useMutation({
    mutationFn: () => api.loadDefaults(workspaceId, selectedProfile),
    onSuccess: () => setStep(4),
  });

  const inviteApprover = useMutation({
    mutationFn: () => api.inviteMember(workspaceId, approverEmail, "approver"),
    onSuccess: () => setStep(5),
  });

  const complete = useMutation({
    mutationFn: () => api.completeOnboarding(workspaceId),
    onSuccess: () => router.push("/dashboard"),
  });

  const STEP_CONTENT = [
    // Step 0: Welcome
    <div key="welcome" className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Welcome to Release Guard</h2>
        <p className="text-slate-500 mt-2">Stop risky releases before they reach production. Set up your workspace in 5 minutes.</p>
      </div>
      <div className="bg-slate-50 rounded-xl border border-border p-5 space-y-3">
        <p className="text-sm font-semibold text-slate-700">What you'll set up:</p>
        {["Connect GitHub and Jira for automatic evidence", "Choose release rules that match your team", "Invite an approver for high-risk releases", "See a blocked and approved release live"].map((item, i) => (
          <div key={i} className="flex items-center gap-3 text-sm text-slate-600">
            <span className="w-5 h-5 rounded-full bg-brand/10 text-brand text-xs flex items-center justify-center font-bold">{i + 1}</span>
            {item}
          </div>
        ))}
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1.5">What's your team called?</label>
        <input value={workspaceName} onChange={e => setWorkspaceName(e.target.value)}
          placeholder="Acme Engineering"
          className="w-full border border-border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
      </div>
      <Button onClick={() => createWorkspace.mutate()} disabled={!workspaceName || createWorkspace.isPending}>
        {createWorkspace.isPending ? "Creating..." : "Get started →"}
      </Button>
    </div>,

    // Step 1: GitHub
    <div key="github" className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Connect GitHub</h2>
        <p className="text-slate-500 mt-2">We'll pull CI/CD results and PR status automatically — no manual entry needed.</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1.5">GitHub personal access token</label>
        <input type="password" value={githubToken} onChange={e => setGithubToken(e.target.value)}
          placeholder="ghp_xxxxxxxxxxxx"
          className="w-full border border-border rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
        <p className="text-xs text-slate-400 mt-1.5">Needs repo and workflow read permissions</p>
      </div>
      <div className="flex gap-2">
        <Button onClick={() => connectGitHub.mutate()} disabled={!githubToken || connectGitHub.isPending}>
          {connectGitHub.isPending ? "Connecting..." : "Connect GitHub →"}
        </Button>
        <Button variant="ghost" onClick={() => setStep(2)}>Skip for now</Button>
      </div>
    </div>,

    // Step 2: Jira
    <div key="jira" className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Connect Jira</h2>
        <p className="text-slate-500 mt-2">Attach tickets to releases as change request evidence.</p>
      </div>
      <div className="space-y-3">
        <input value={jiraUrl} onChange={e => setJiraUrl(e.target.value)}
          placeholder="https://yourteam.atlassian.net"
          className="w-full border border-border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
        <input value={jiraEmail} onChange={e => setJiraEmail(e.target.value)}
          placeholder="your.email@company.com"
          className="w-full border border-border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
        <input type="password" value={jiraToken} onChange={e => setJiraToken(e.target.value)}
          placeholder="Jira API token"
          className="w-full border border-border rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
      </div>
      <div className="flex gap-2">
        <Button onClick={() => connectJira.mutate()} disabled={!jiraUrl || connectJira.isPending}>
          {connectJira.isPending ? "Connecting..." : "Connect Jira →"}
        </Button>
        <Button variant="ghost" onClick={() => setStep(3)}>Skip for now</Button>
      </div>
    </div>,

    // Step 3: Profile
    <div key="profile" className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Choose your release rules</h2>
        <p className="text-slate-500 mt-2">Pick a preset. You can change this at any time.</p>
      </div>
      <div className="space-y-3">
        {PROFILES.map(p => (
          <button key={p.id} onClick={() => setSelectedProfile(p.id)}
            className={cn(
              "w-full text-left p-4 rounded-xl border-2 transition-all",
              selectedProfile === p.id ? "border-brand bg-brand/5" : "border-border bg-white hover:bg-surface-raised"
            )}>
            <p className="font-semibold text-sm text-slate-800">{p.label}</p>
            <p className="text-xs text-slate-500 mt-0.5">{p.desc}</p>
          </button>
        ))}
      </div>
      <Button onClick={() => loadDefaults.mutate()} disabled={loadDefaults.isPending}>
        {loadDefaults.isPending ? "Applying..." : "Apply rules →"}
      </Button>
    </div>,

    // Step 4: Invite
    <div key="invite" className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Invite an approver</h2>
        <p className="text-slate-500 mt-2">High-risk releases need a human review. Who should approve them?</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1.5">Approver email</label>
        <input value={approverEmail} onChange={e => setApproverEmail(e.target.value)}
          placeholder="manager@company.com"
          className="w-full border border-border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand" />
      </div>
      <div className="flex gap-2">
        <Button onClick={() => inviteApprover.mutate()} disabled={!approverEmail || inviteApprover.isPending}>
          {inviteApprover.isPending ? "Inviting..." : "Invite approver →"}
        </Button>
        <Button variant="ghost" onClick={() => setStep(5)}>Skip for now</Button>
      </div>
    </div>,

    // Step 5: Done
    <div key="done" className="space-y-6 text-center">
      <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center text-3xl mx-auto">✓</div>
      <div>
        <h2 className="text-2xl font-bold text-slate-800">You're all set</h2>
        <p className="text-slate-500 mt-2">Release Guard is active. Create your first release request.</p>
      </div>
      <Button onClick={() => complete.mutate()} disabled={complete.isPending}>
        {complete.isPending ? "Finishing..." : "Go to dashboard →"}
      </Button>
    </div>,
  ];

  return (
    <div className="min-h-screen bg-surface-raised flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="flex items-center gap-2 mb-8 justify-center">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex items-center gap-2">
              <div className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors",
                i < step ? "bg-brand text-white" : i === step ? "bg-brand/20 text-brand border-2 border-brand" : "bg-slate-200 text-slate-400"
              )}>
                {i < step ? "✓" : s.number}
              </div>
              {i < STEPS.length - 1 && (
                <div className={cn("w-8 h-0.5 transition-colors", i < step ? "bg-brand" : "bg-slate-200")} />
              )}
            </div>
          ))}
        </div>
        <div className="bg-white rounded-2xl border border-border p-8 shadow-sm">
          {STEP_CONTENT[step]}
        </div>
      </div>
    </div>
  );
}
