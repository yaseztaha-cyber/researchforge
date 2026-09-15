"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function HistoryPage() {
  const [runs, setRuns] = useState<{ run_id: string; question: string; status: string; started_at: string }[]>([]);
  useEffect(() => { api.runs().then((r) => setRuns(r.runs)).catch(() => setRuns([])); }, []);
  return (
    <section style={{ padding: "24px 0 60px" }}>
      <h1 style={{ fontFamily: "Georgia, serif" }}>Research history</h1>
      <div className="card">
        {runs.length === 0 && <p className="meta">No research runs yet.</p>}
        <table className="tbl">
          <thead><tr><th>Question</th><th>Status</th><th>Started</th><th></th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.run_id}>
                <td>{r.question}</td><td>{r.status}</td><td>{new Date(r.started_at).toLocaleString()}</td>
                <td><a href={`/research/${r.run_id}`}>Open</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
