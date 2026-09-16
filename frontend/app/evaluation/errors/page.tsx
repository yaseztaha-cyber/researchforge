"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ErrorsPage() {
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [errors, setErrors] = useState<{id:string; query:string; error_type:string; severity:string; notes:string|null}[]>([]);
  const [filter, setFilter] = useState("");
  useEffect(() => {
    fetch(`${API}/api/eval/errors/summary`).then(r=>r.json()).then(setSummary).catch(()=>{});
    fetch(`${API}/api/eval/errors/`).then(r=>r.json()).then(d=>setErrors(d.errors||[])).catch(()=>{});
  }, []);
  const filtered = filter ? errors.filter(e=>e.error_type===filter) : errors;
  return (
    <section style={{padding:"24px 0 60px"}}>
      <h1 style={{fontFamily:"Georgia, serif"}}>Retrieval Error Analysis</h1>
      <p className="meta">10-category taxonomy. Every error is a real failure from evaluation runs — not fabricated.</p>
      <div className="card">
        <h2>Summary</h2>
        {!summary && <p className="meta">Loading…</p>}
        {summary && <pre style={{whiteSpace:"pre-wrap", fontSize:13}}>{JSON.stringify(summary, null, 2)}</pre>}
      </div>
      <div className="card" style={{marginTop:12}}>
        <h2>Errors</h2>
        <div className="row">
          <label>Filter by type:
            <select value={filter} onChange={e=>setFilter(e.target.value)}>
              <option value="">All</option>
              {["wrong_domain","wrong_source","right_source_wrong_chunk","right_chunk_wrong_rank","missing_source","duplicate_source","query_decomposition_failure","evidence_extraction_failure","source_metadata_failure","conflict_misclassification"].map(t=><option key={t} value={t}>{t}</option>)}
            </select>
          </label>
        </div>
        <table className="tbl">
          <thead><tr><th>Query</th><th>Type</th><th>Severity</th><th>Notes</th></tr></thead>
          <tbody>
            {filtered.map(e=><tr key={e.id}><td>{e.query.slice(0,80)}</td><td>{e.error_type}</td><td>{e.severity}</td><td>{e.notes||""}</td></tr>)}
            {filtered.length===0 && <tr><td colSpan={4} className="meta">No errors yet. Run evaluation and annotate failures.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
