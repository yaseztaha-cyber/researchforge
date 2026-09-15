"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface RunRow {
  run_id: string; question: string; status: string; started_at: string;
  mode: string; confidence: string | null; num_sources: number; num_claims: number;
}

export default function HistoryPage() {
  const [runs, setRuns] = useState<RunRow[]>([]);
  useEffect(() => { api.runs().then((r) => setRuns(r.runs)).catch(() => setRuns([])); }, []);
  return (
    <section style={{ padding: "24px 0 60px" }}>
      <h1 style={{ fontFamily: "Georgia, serif" }}>Research history</h1>
      <div className="card">
        {runs.length === 0 && <p className="meta">No research runs yet.</p>}
        <table className="tbl">
          <thead><tr><th>Question</th><th>Mode</th><th>Status</th><th>Sources</th><th>Claims</th><th>Confidence</th><th>Started</th><th></th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.run_id}>
                <td>{r.question}</td><td>{r.mode}</td><td>{r.status}</td>
                <td>{r.num_sources}</td><td>{r.num_claims}</td><td>{r.confidence || "—"}</td>
                <td>{new Date(r.started_at).toLocaleString()}</td>
                <td><a href={`/research/${r.run_id}`}>Open</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
