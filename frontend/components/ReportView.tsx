"use client";
import type { ClaimItem, ReportData } from "@/types";

function renderWithCites(text: string, onSelect: (id: string | null) => void) {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((p, i) => {
    const m = p.match(/\[(\d+)\]/);
    if (!m) return <span key={i}>{p}</span>;
    return (
      <button key={i} className="cite" aria-label={`Open citation ${m[1]}`} onClick={() => onSelect(m[1])}>
        [{m[1]}]
      </button>
    );
  });
}

export default function ReportView({ report, claims, onSelect, onClaim }: {
  report: ReportData; claims: ClaimItem[];
  onSelect: (s: string | null) => void; onClaim: (claimId: string | null) => void;
}) {
  const claimByText = (t: string) => claims.find((c) => t.includes(c.claim_text.slice(0, 60)));
  return (
    <article className="card" aria-label="Research report">
      {report.mock_mode && <div className="mock-banner">Mock/dev sources — fixture citations, not live literature.</div>}
      <p className="meta">Research Question · mode: {report.mode}{report.stop_reason ? ` · stopped: ${report.stop_reason}` : ""}</p>
      <h2 style={{ fontFamily: "Georgia, serif", marginTop: 0 }}>{report.question}</h2>
      <details><summary>Research method</summary><p className="meta">{report.research_method || "Not recorded."}</p>
        {report.stage_ms && <p className="meta">Stage latency (ms): <code>{JSON.stringify(report.stage_ms)}</code></p>}
        {report.cost && (report.cost.llm_calls > 0 || report.cost.search_calls > 0) && (
          <p className="meta">Cost trace: <code>{JSON.stringify(report.cost)}</code></p>)}
      </details>
      <h2 className="sec">Executive Summary</h2>
      <p>{report.executive_summary}</p>
      {report.confidence && (
        <p>
          <span className="badge">Confidence: {report.confidence.label} ({Math.round(report.confidence.overall * 100)}%)</span>
          <span className="meta">coverage {Math.round(report.confidence.evidence_coverage * 100)}% · agreement {Math.round(report.confidence.source_agreement * 100)}% · quality {Math.round(report.confidence.source_quality * 100)}% · contradictions {report.confidence.contradiction_level}</span>
          {report.confidence.method && <span className="meta"><br />{report.confidence.method}</span>}
        </p>
      )}
      <h2 className="sec">Key Findings</h2>
      <p className="meta">Select a finding title to inspect its evidence (“show me why”).</p>
      {report.findings.map((f, i) => {
        const linked = claimByText(f.text);
        return (
          <div className="finding" key={i}>
            <h3>{i + 1}. {linked ? (
              <button className="ghost" style={{ textAlign: "left", fontSize: "1em", fontWeight: 700 }}
                onClick={() => onClaim(linked.id)} title="Show me why — inspect evidence for this claim">
                {f.title} {linked.supported ? "✓" : "✗"}
              </button>) : f.title}</h3>
            <p>{renderWithCites(f.text, onSelect)}</p>
          </div>
        );
      })}
      {report.conflicts.length > 0 && (
        <>
          <h2 className="sec">Conflicting Evidence</h2>
          {report.conflicts.map((c, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }} className="ev">
              <div style={{ gridColumn: "1 / -1" }}><strong>{c.topic}</strong>{" "}
                <span className="badge">{c.classification || "unclear"}</span></div>
              <div><strong>Position A</strong><blockquote>“{c.position_a}”</blockquote></div>
              <div><strong>Position B</strong><blockquote>“{c.position_b}”</blockquote></div>
              <p className="meta" style={{ gridColumn: "1 / -1" }}>Possible reason: {c.possible_reason}</p>
            </div>
          ))}
        </>
      )}
      <h2 className="sec">Uncertainties</h2>
      <ul>{report.uncertainties.map((u, i) => <li key={i}>{u}</li>)}</ul>
      <h2 className="sec">Conclusion</h2>
      <p>{report.conclusion}</p>
      <h2 className="sec">Sources</h2>
      <ol>
        {report.citations.map((c) => (
          <li key={c.index} id={`cite-${c.index}`}>
            <button className="cite" onClick={() => onSelect(c.source_id)}>[{c.index}]</button> {c.source_title}
            {c.url && <> — <a href={c.url}>{c.url}</a></>}
            {c.section && <span className="meta"> · {c.section}{c.page ? ` · p.${c.page}` : ""}</span>}
          </li>
        ))}
      </ol>
    </article>
  );
}
