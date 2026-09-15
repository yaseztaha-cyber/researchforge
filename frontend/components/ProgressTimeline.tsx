"use client";
const STAGES = ["planning", "searching", "filtering", "extracting", "analyzing", "synthesizing", "verifying", "done"];
const LABELS: Record<string, string> = {
  planning: "Research question analyzed", searching: "Research plan created · sources discovering",
  filtering: "Sources filtered", extracting: "Evidence extracted", analyzing: "Cross-checking claims",
  synthesizing: "Writing report", verifying: "Verifying citations", done: "Completed", failed: "Failed", queued: "Queued"
};

export default function ProgressTimeline({ stage, progress, status, detail, counts }: { stage: string; progress: number; status: string; detail: string; counts?: Record<string, number> }) {
  const idx = STAGES.indexOf(stage);
  return (
    <div>
      <div className="progressbar" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Research progress">
        <div style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      <ul className="timeline" style={{ marginTop: 12 }}>
        {STAGES.map((s, i) => (
          <li key={s} className={i < idx || status === "completed" ? "done" : i === idx ? "active" : ""}>
            <span className="dot" aria-hidden />{LABELS[s] || s}{i === idx && detail ? ` — ${detail}` : ""}
          </li>
        ))}
      </ul>
      <p className="meta">Status: {status} · {Math.round(progress * 100)}%
        {counts && Object.keys(counts).length > 0 && (
          <> · {Object.entries(counts).map(([k, v]) => `${k}: ${v}`).join(" · ")}</>
        )}</p>
    </div>
  );
}
