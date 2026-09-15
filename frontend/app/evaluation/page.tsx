"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function EvalPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { api.evalDashboard().then(setData).catch(() => setData(null)); }, []);
  return (
    <section style={{ padding: "24px 0 60px" }}>
      <h1 style={{ fontFamily: "Georgia, serif" }}>Evaluation dashboard</h1>
      <p className="meta">Engineering metrics computed from real runs — never fabricated.</p>
      <div className="card">
        {!data && <p className="meta">Loading…</p>}
        {data && (
          <table className="tbl">
            <tbody>
              {Object.entries(data).map(([k, v]) => (
                <tr key={k}><th>{k}</th><td><code>{JSON.stringify(v)}</code></td></tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
