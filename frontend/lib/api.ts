const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) }
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text.slice(0, 400)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<{ status: string; mock_mode: boolean; llm_provider: string; search_provider: string }>("/api/health"),
  createResearch: (question: string, depth: "standard" | "deep", max_sources?: number) =>
    req<{ run_id: string; status: string }>("/api/research", {
      method: "POST",
      body: JSON.stringify({ question, depth, max_sources })
    }),
  progress: (id: string) =>
    req<{ stage: string; progress: number; status: string; detail: string; mock_mode: boolean }>(`/api/research/${id}/progress`),
  result: (id: string) =>
    req<{ status: string; stage: string; progress: number; question: string; plan: unknown; num_sources: number; num_claims: number; error: string | null; mock_mode: boolean }>(`/api/research/${id}`),
  sources: (id: string) => req<{ sources: import("@/types").SourceItem[] }>(`/api/research/${id}/sources`),
  evidence: (id: string) => req<{ evidence: import("@/types").EvidenceItem[] }>(`/api/research/${id}/evidence`),
  claims: (id: string) => req<{ claims: import("@/types").ClaimItem[] }>(`/api/research/${id}/claims`),
  report: (id: string) => req<import("@/types").ReportData>(`/api/research/${id}/report`),
  sourceDetail: (id: string) => req<Record<string, unknown>>(`/api/sources/${id}`),
  runs: () => req<{ runs: { run_id: string; question: string; status: string; started_at: string }[] }>("/api/research"),
  evalDashboard: () => req<Record<string, unknown>>("/api/eval/dashboard"),
  exportUrl: (id: string, fmt: "md" | "json") => `${API}/api/research/${id}/export.${fmt}`
};

export const API_BASE = API;
