"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { GraphData } from "@/types";

const COLORS: Record<string, string> = {
  question: "#1a5632", subquestion: "#3a6ea5", claim: "#8a5a00",
  evidence: "#5a4a8a", source: "#444444"
};

/** Minimal dependency-free SVG graph with an accessible list fallback. */
export default function ResearchGraph({ runId }: { runId: string }) {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    api.graph(runId).then(setGraph).catch(() => setGraph(null));
  }, [runId]);

  if (!graph) return <div className="card"><p className="meta">Loading research graph…</p></div>;

  // Layered layout by node type; x spreads within layer.
  const layers = ["question", "subquestion", "claim", "evidence", "source"];
  const byLayer = layers.map((t) => graph.nodes.filter((n) => n.type === t));
  const W = 760, H = 120 + 110 * layers.length;
  const pos = new Map<string, { x: number; y: number }>();
  byLayer.forEach((nodes, li) => {
    nodes.forEach((n, i) => {
      pos.set(n.id, { x: 60 + (W - 120) * (nodes.length === 1 ? 0.5 : i / (nodes.length - 1)), y: 60 + li * 110 });
    });
  });
  const sel = graph.nodes.find((n) => n.id === selected);

  return (
    <div className="card" aria-label="Research graph">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong>Research graph</strong>
        <span>
          <button className="ghost" onClick={() => setZoom(Math.max(0.5, +(zoom - 0.2).toFixed(1)))} aria-label="Zoom out">−</button>{" "}
          <button className="ghost" onClick={() => setZoom(Math.min(2, +(zoom + 0.2).toFixed(1)))} aria-label="Zoom in">+</button>
        </span>
      </div>
      <div style={{ overflow: "auto" }}>
        <svg width={W * zoom} height={H * zoom} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Question to source graph">
          {graph.edges.map((e, i) => {
            const a = pos.get(e.from), b = pos.get(e.to);
            if (!a || !b) return null;
            return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#c9c4b8" strokeWidth={1} />;
          })}
          {graph.nodes.map((n) => {
            const p = pos.get(n.id);
            if (!p) return null;
            return (
              <g key={n.id} onClick={() => setSelected(n.id)} style={{ cursor: "pointer" }} role="button" aria-label={n.label} tabIndex={0}
                onKeyDown={(ev) => { if (ev.key === "Enter") setSelected(n.id); }}>
                <circle cx={p.x} cy={p.y} r={n.id === selected ? 13 : 10} fill={COLORS[n.type] || "#666"}
                  stroke={n.id === selected ? "#000" : "none"} strokeWidth={2} />
                <text x={p.x} y={p.y + 26} textAnchor="middle" fontSize={10} fill="#333">
                  {n.label.length > 34 ? n.label.slice(0, 34) + "…" : n.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      {sel && (
        <div className="ev">
          <strong>{sel.type}</strong>: {sel.label}
          {sel.source_type && <span className="meta"> · {sel.source_type} · {sel.origin}</span>}
          {sel.supported !== undefined && sel.type === "claim" && (
            <span className="meta"> · {sel.supported ? "supported" : "unsupported"}</span>)}
        </div>
      )}
      <details>
        <summary>List view (accessible alternative)</summary>
        <ul>
          {graph.nodes.map((n) => (
            <li key={n.id}><span className="badge">{n.type}</span>{n.label}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}
