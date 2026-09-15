"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface TimelineData {
  sources: { source_id: string; title: string; url: string | null; publisher: string | null; source_type: string; domain: string | null; origin: string; published_at: string | null; parsed_date: string | null; is_approximate: boolean; relevance_score: number }[];
  claim_timeline: { claim_id: string; claim_text: string; claim_type: string; supported: boolean; sub_question: string | null; first_evidence: { evidence_id: string; quote: string; source_id: string } | null; latest_evidence: { evidence_id: string; quote: string; source_id: string } | null; supporting_count: number }[];
  conflict_timeline: { topic: string; classification: string; position_a: string; source_a: string; source_a_date: string | null; position_b: string; source_b: string; source_b_date: string | null; possible_reason: string }[];
  note: string;
}

export default function EvidenceTimeline({ runId, onSelectSource }: { runId: string; onSelectSource: (id: string) => void }) {
  const [data, setData] = useState<TimelineData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/research/${runId}/timeline`)
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(setData).catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, [runId]);

  if (error) return <div className="card"><p role="alert" style={{ color: "#9b1c1c" }}>{error}</p></div>;
  if (!data) return <div className="card"><p className="meta">Loading timeline…</p></div>;

  return (
    <div className="card" aria-label="Evidence timeline">
      <h2 style={{ marginTop: 0 }}>Evidence timeline</h2>
      <p className="meta">{data.note}</p>
      <h3>Sources chronology</h3>
      {data.sources.length === 0 && <p className="meta">No sources.</p>}
      <ol style={{ borderLeft: "2px solid #e6e2da", paddingLeft: 16 }}>
        {data.sources.map((s) => (
          <li key={s.source_id} style={{ margin: "10px 0" }}>
            <strong>{s.parsed_date ? new Date(s.parsed_date).toISOString().slice(0, 10) : "Undated"}</strong>
            {s.is_approximate && <span className="meta"> (approx.)</span>} — {s.title}
            <span className="badge">{s.source_type}</span><span className="badge">{s.origin}</span>
            <button className="ghost" style={{ marginLeft: 8 }} onClick={() => onSelectSource(s.source_id)}>Inspect</button>
            {s.published_at && <span className="meta"> · published: {s.published_at}</span>}
          </li>
        ))}
      </ol>
      <h3>Claim chronology</h3>
      {data.claim_timeline.map((c) => (
        <div key={c.claim_id} className="ev">
          <strong>{c.claim_text.slice(0, 120)}</strong> <span className="badge">{c.claim_type}</span>
          <p className="meta">Sub-question: {c.sub_question || "—"} · Supporting evidence: {c.supporting_count}</p>
          {c.first_evidence && <blockquote>First: “{c.first_evidence.quote.slice(0, 180)}”</blockquote>}
          {c.latest_evidence && c.latest_evidence.evidence_id !== c.first_evidence?.evidence_id && (
            <blockquote>Latest: “{c.latest_evidence.quote.slice(0, 180)}”</blockquote>
          )}
        </div>
      ))}
      {data.conflict_timeline.length > 0 && (
        <>
          <h3>Conflict chronology</h3>
          {data.conflict_timeline.map((cf, i) => (
            <div key={i} className="ev">
              <strong>{cf.topic}</strong> <span className="badge">{cf.classification || "unclear"}</span>
              <p>{cf.source_a_date || "undated"}: “{cf.position_a}”</p>
              <p>{cf.source_b_date || "undated"}: “{cf.position_b}”</p>
              <p className="meta">{cf.possible_reason}</p>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
