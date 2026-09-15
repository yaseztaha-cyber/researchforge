"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ClaimTrace } from "@/types";

export default function ClaimInspector({ runId, claimId, onClose }: { runId: string; claimId: string; onClose: () => void }) {
  const [trace, setTrace] = useState<ClaimTrace | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.claimTrace(runId, claimId).then(setTrace).catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, [runId, claimId]);

  return (
    <div role="dialog" aria-modal="false" aria-label="Claim evidence inspector" className="card"
      style={{ borderColor: "#1a5632", margin: "12px 0" }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong>Show me why — claim trace</strong>
        <button className="ghost" onClick={onClose} aria-label="Close inspector">Close</button>
      </div>
      {error && <p role="alert" style={{ color: "#9b1c1c" }}>{error}</p>}
      {!trace && !error && <p className="meta">Loading trace…</p>}
      {trace && (
        <>
          <p><strong>Claim:</strong> {trace.claim.claim_text}</p>
          <p className="meta">Type: {trace.claim.claim_type} · Confidence {Math.round(trace.claim.confidence * 100)}% ·
            Supported: {trace.claim.supported ? "Yes" : "No"}</p>
          {trace.claim.sub_question && <p className="meta">Answers sub-question: {trace.claim.sub_question}</p>}
          {trace.agreement && (
            <p><span className="badge">{trace.agreement.supporting} supporting</span>
              <span className="badge">{trace.agreement.contradicting} contradicting</span>
              <span className="badge">{trace.agreement.neutral} neutral</span>
              <span className="meta"> {trace.agreement.note}</span></p>
          )}
          <h3>Supporting evidence</h3>
          {trace.supporting.length === 0 && <p className="meta">Insufficient evidence — no supporting passages.</p>}
          {trace.supporting.map((s) => (
            <div className="ev" key={s.evidence_id}>
              <blockquote>“{s.quote}”</blockquote>
              {s.source && (
                <>
                  <p><strong>{s.source.title}</strong> <span className="badge">{s.source.source_type}</span>
                    <span className="badge">{s.source.origin}</span></p>
                  <p className="meta">{s.source.publisher} · {s.source.domain} ·
                    {s.section ? ` ${s.section}` : ""}{s.page ? ` · p.${s.page}` : ""} ·
                    relevance {s.source.relevance_score} · quality {s.source.quality_score}</p>
                  {s.source.url && <a href={s.source.url}>{s.source.url}</a>}
                  <details><summary>Why this source ranked here</summary>
                    <ul>{s.source.ranking_reasons.map((r, i) => <li key={i} className="meta">{r}</li>)}</ul>
                    {s.source.score_breakdown && <p className="meta"><code>{JSON.stringify(s.source.score_breakdown)}</code></p>}
                  </details>
                </>
              )}
            </div>
          ))}
          {trace.related_conflicts.length > 0 && (
            <>
              <h3>Contradicting evidence</h3>
              {trace.related_conflicts.map((c, i) => (
                <div className="ev" key={i}>
                  <p className="meta">Classification: <strong>{c.classification || "unclear"}</strong></p>
                  <blockquote>“{c.position_a}”</blockquote>
                  <blockquote>“{c.position_b}”</blockquote>
                  <p className="meta">{c.possible_reason}</p>
                </div>
              ))}
            </>
          )}
          <h3>Verification</h3>
          <ul>
            <li>Supported: {trace.verification.supported ? "Yes" : "No"}</li>
            <li>Citation valid: {trace.verification.citation_valid ? "Yes" : "No"}</li>
            <li>Potential overstatement: {trace.verification.potential_overstatement ? "Yes" : "No"}</li>
            {trace.verification.issues.map((iss, i) => <li key={i}>{iss}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}
