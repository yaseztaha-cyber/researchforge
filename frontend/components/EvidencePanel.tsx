"use client";
import { useState } from "react";
import type { SourceItem, EvidenceItem, ClaimItem } from "@/types";

export default function EvidencePanel({ sources, evidence, claims, selected, onSelect }: {
  sources: SourceItem[]; evidence: EvidenceItem[]; claims: ClaimItem[];
  selected: string | null; onSelect: (s: string | null) => void;
}) {
  const [open, setOpen] = useState<string | null>(selected);
  const shown = selected
    ? evidence.filter((e) => e.source_id === selected || e.id === selected || String(selected).startsWith(e.source_id))
    : evidence;
  const activeSource = sources.find((s) => s.id === (selected || open));

  return (
    <aside className="card" aria-label="Evidence and sources">
      <h2 style={{ marginTop: 0 }}>Evidence &amp; Sources</h2>
      <p className="meta">{sources.length} sources · {evidence.length} passages · {claims.filter((c) => c.supported).length}/{claims.length} claims supported</p>
      {activeSource && (
        <div className="ev" style={{ borderColor: "#1a5632" }}>
          <strong>{activeSource.title}</strong>
          <p className="meta">{activeSource.publisher} · {activeSource.source_type} · {activeSource.domain}</p>
          <p className="meta">Relevance {activeSource.relevance_score} · Quality {activeSource.quality_score}</p>
          {activeSource.url && <a href={activeSource.url}>{activeSource.url}</a>}
          <p>{activeSource.description}</p>
          <button className="ghost" onClick={() => onSelect(null)}>Clear selection</button>
        </div>
      )}
      <h3>Sources</h3>
      {sources.map((s) => (
        <div key={s.id} style={{ marginBottom: 6 }}>
          <button className="ghost" style={{ width: "100%", textAlign: "left" }} onClick={() => { onSelect(s.id); setOpen(s.id); }}>
            <span className="badge">{s.source_type}</span>{s.title}
          </button>
          {open === s.id && (
            <div className="ev">
              <p className="meta">{s.publisher} · {s.domain} · relevance {s.relevance_score} · quality {s.quality_score}</p>
              {s.score_breakdown && <p className="meta">Scoring: <code>{JSON.stringify(s.score_breakdown)}</code></p>}
              {evidence.filter((e) => e.source_id === s.id).map((e) => (
                <div key={e.id}><p><strong>Claim:</strong> {e.claim}</p><blockquote>“{e.quote}”</blockquote></div>
              ))}
            </div>
          )}
        </div>
      ))}
      <h3>All evidence</h3>
      {(selected ? shown : evidence).slice(0, 20).map((e) => (
        <div className="ev" key={e.id}>
          <p><strong>{e.claim}</strong></p>
          <blockquote>“{e.quote}”</blockquote>
          <p className="meta">{e.section || "no section"} · relevance {e.relevance_score} · confidence {e.confidence_score}</p>
        </div>
      ))}
      <h3>Claims</h3>
      <ul>
        {claims.map((c) => (
          <li key={c.id}>{c.supported ? "✓" : "✗"} {c.claim_text} <span className="meta">({c.claim_type}, {Math.round(c.confidence * 100)}%)</span></li>
        ))}
      </ul>
    </aside>
  );
}
