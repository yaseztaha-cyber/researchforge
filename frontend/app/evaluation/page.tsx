"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function EvalPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { api.evalDashboard().then(setData).catch(() => setData(null)); }, []);
  const versions = (data?.benchmark_versions as { file: string; version: string; n: number; aggregate: Record<string, number> }[] | undefined) || [];
  const main = { ...(data || {}) };
  delete main.benchmark_versions;
  return (
    <section style={{ padding: "24px 0 60px" }}>
      <h1 style={{ fontFamily: "Georgia, serif" }}>Evaluation dashboard</h1>
      <p className="meta">Engineering metrics computed from real runs — never fabricated.</p>
      <div className="card">
        <h2>Live database metrics</h2>
        {!data && <p className="meta">Loading…</p>}
        {data && (
          <table className="tbl">
            <tbody>
              {Object.entries(main).map(([k, v]) => (
                <tr key={k}><th>{k}</th><td><code>{JSON.stringify(v)}</code></td></tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h2>Versioned benchmark reports</h2>
        {versions.length === 0 && <p className="meta">No benchmark reports yet. Run <code>python evaluation/scripts/run_evaluation.py --out evaluation/reports/v0.2_mock.json</code>.</p>}
        {versions.map((v) => (
          <div key={v.file} style={{ marginBottom: 10 }}>
            <strong>{v.version || v.file}</strong> <span className="meta">({v.n} runs)</span>
            <table className="tbl">
              <tbody>
                {Object.entries(v.aggregate || {}).map(([k, val]) => (
                  <tr key={k}><th>{k}</th><td><code>{JSON.stringify(val)}</code></td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </section>
  );
}
