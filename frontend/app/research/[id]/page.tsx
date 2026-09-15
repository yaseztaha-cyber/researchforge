"use client";
import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useResearch } from "@/hooks/useResearch";
import ProgressTimeline from "@/components/ProgressTimeline";
import ReportView from "@/components/ReportView";
import EvidencePanel from "@/components/EvidencePanel";
import type { ReportData, SourceItem, EvidenceItem, ClaimItem } from "@/types";

export default function ResearchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { stage, progress, status, detail } = useResearch(id);
  const [report, setReport] = useState<ReportData | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [claims, setClaims] = useState<ClaimItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState("");

  const finished = status === "completed" || status === "partial" || status === "failed";

  useEffect(() => {
    if (!finished) return;
    (async () => {
      try {
        const [rep, s, e, c] = await Promise.all([
          api.report(id).catch(() => null), api.sources(id), api.evidence(id), api.claims(id)
        ]);
        if (rep) setReport(rep);
        setSources(s.sources); setEvidence(e.evidence); setClaims(c.claims);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load report.");
      }
    })();
  }, [finished, id]);

  return (
    <section style={{ padding: "24px 0 60px" }}>
      <h1 style={{ fontFamily: "Georgia, serif" }}>Research workspace</h1>
      <div className="card" aria-live="polite">
        <ProgressTimeline stage={stage} progress={progress} status={status} detail={detail} />
      </div>
      {error && <p role="alert" style={{ color: "#9b1c1c" }}>{error}</p>}
      {report && (
        <>
          <div style={{ margin: "12px 0", display: "flex", gap: 8 }}>
            <a href={api.exportUrl(id, "md")}><button className="ghost">Export Markdown</button></a>
            <a href={api.exportUrl(id, "json")}><button className="ghost">Export JSON</button></a>
            <button className="ghost" onClick={() => window.print()}>Print / PDF</button>
          </div>
          <div className="grid2">
            <ReportView report={report} onSelect={setSelected} selected={selected} />
            <EvidencePanel sources={sources} evidence={evidence} claims={claims} selected={selected} onSelect={setSelected} />
          </div>
        </>
      )}
      {finished && !report && !error && (
        <div className="card"><p><strong>{status === "failed" ? "Research failed." : "Partial success — no report."}</strong> Check history or try again with a broader question.</p></div>
      )}
    </section>
  );
}
