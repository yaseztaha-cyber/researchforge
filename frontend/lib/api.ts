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

export interface CreateOpts {
  depth: "standard" | "deep";
  mode: "web" | "private" | "hybrid";
  document_ids: string[];
  max_sources?: number;
  max_rounds?: number;
  strictness?: "lenient" | "standard" | "strict";
}

export const api = {
  health: () => req<{ status: string; mock_mode: boolean; llm_provider: string; search_provider: string }>("/api/health"),
  createResearch: (question: string, opts: CreateOpts) =>
    req<{ run_id: string; status: string }>("/api/research", {
      method: "POST",
      body: JSON.stringify({
        question, depth: opts.depth, mode: opts.mode, document_ids: opts.document_ids,
        max_sources: opts.max_sources, max_rounds: opts.max_rounds, strictness: opts.strictness
      })
    }),
  progress: (id: string) =>
    req<{ stage: string; progress: number; status: string; detail: string; mock_mode: boolean; mode: string; counts: Record<string, number>; num_sources: number; num_claims: number }>(`/api/research/${id}/progress`),
  result: (id: string) =>
    req<{ status: string; stage: string; progress: number; question: string; plan: unknown; num_sources: number; num_claims: number; error: string | null; mock_mode: boolean; mode: string; stop_reason: string | null; stage_ms: Record<string, number> | null; cost: Record<string, number> }>(`/api/research/${id}`),
  queries: (id: string) => req<{ queries: { query: string; query_type: string; reason: string; round_number: number; status: string; hits: number }[] }>(`/api/research/${id}/queries`),
  sources: (id: string) => req<{ sources: import("@/types").SourceItem[] }>(`/api/research/${id}/sources`),
  evidence: (id: string) => req<{ evidence: import("@/types").EvidenceItem[] }>(`/api/research/${id}/evidence`),
  claims: (id: string) => req<{ claims: import("@/types").ClaimItem[] }>(`/api/research/${id}/claims`),
  claimTrace: (runId: string, claimId: string) =>
    req<import("@/types").ClaimTrace>(`/api/research/${runId}/claims/${claimId}/trace`),
  graph: (id: string) => req<import("@/types").GraphData>(`/api/research/${id}/graph`),
  report: (id: string) => req<import("@/types").ReportData>(`/api/research/${id}/report`),
  sourceDetail: (id: string) => req<Record<string, unknown>>(`/api/sources/${id}`),
  runs: () => req<{ runs: { run_id: string; question: string; status: string; started_at: string; mode: string; confidence: string | null; num_sources: number; num_claims: number }[] }>("/api/research"),
  evalDashboard: () => req<Record<string, unknown>>("/api/eval/dashboard"),
  upload: async (file: File, runId?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API}/api/documents/upload${runId ? `?run_id=${runId}` : ""}`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`Upload failed (${res.status}): ${(await res.text()).slice(0, 300)}`);
    return res.json() as Promise<{ document_id: string; duplicate: boolean; num_chunks: number }>;
  },
  exportUrl: (id: string, fmt: "md" | "json") => `${API}/api/research/${id}/export.${fmt}`
};

export const API_BASE = API;
