"use client";
import type { ReportData } from "@/types";

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

export default function ReportView({ report, onSelect, selected }: { report: ReportData; onSelect: (s: string | null) => void; selected: string | null }) {
  return (
    <article className="card" aria-label="Research report">
      {report.mock_mode && <div className="mock-banner">Mock/dev sources — fixture citations, not live literature.</div>}
      <p className="meta">Research Question</p>
      <h2 style={{ fontFamily: "Georgia, serif", marginTop: 0 }}>{report.question}</h2>
      <h2 className="sec">Executive Summary</h2>
      <p>{report.executive_summary}</p>
      {report.confidence && (
        <p>
          <span className="badge">Confidence: {report.confidence.label} ({Math.round(report.confidence.overall * 100)}%)</span>
          <span className="meta">coverage {Math.round(report.confidence.evidence_coverage * 100)}% · agreement {Math.round(report.confidence.source_agreement * 100)}% · quality {Math.round(report.confidence.source_quality * 100)}% · contradictions {report.confidence.contradiction_level}</span>
        </p>
      )}
      <h2 className="sec">Key Findings</h2>
      {report.findings.map((f, i) => (
        <div className="finding" key={i}>
          <h3>{i + 1}. {f.title}</h3>
          <p>{renderWithCites(f.text, onSelect)}</p>
        </div>
      ))}
      {report.conflicts.length > 0 && (
        <>
          <h2 className="sec">Conflicting Evidence</h2>
          {report.conflicts.map((c, i) => (
            <div className="ev" key={i}>
              <strong>{c.topic}</strong>
              <blockquote>“{c.position_a}”</blockquote>
              <blockquote>“{c.position_b}”</blockquote>
              <p className="meta">Possible reason: {c.possible_reason}</p>
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
