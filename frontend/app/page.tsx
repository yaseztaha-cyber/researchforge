"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, API_BASE } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [question, setQuestion] = useState("What are the environmental impacts of desalination?");
  const [depth, setDepth] = useState<"standard" | "deep">("standard");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mock, setMock] = useState<boolean | null>(null);
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    api.health().then((h) => setMock(h.mock_mode)).catch(() => setMock(null));
  }, []);

  async function start() {
    if (question.trim().length < 5) { setError("Please enter a research question."); return; }
    setBusy(true); setError("");
    try {
      let runId: string | null = null;
      const r = await api.createResearch(question.trim(), depth);
      runId = r.run_id;
      if (file && runId) {
        const fd = new FormData();
        fd.append("file", file);
        await fetch(`${API_BASE}/api/documents/upload?run_id=${runId}`, { method: "POST", body: fd });
      }
      router.push(`/research/${runId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start research.");
      setBusy(false);
    }
  }

  return (
    <>
      <section className="hero">
        <h1>ResearchForge</h1>
        <p className="tag">Research with evidence, not guesses.</p>
        {mock === true && (
          <div className="mock-banner" role="status">
            Development/mock mode is active: results use labeled fixture sources. Configure SEARCH_API_KEY + LLM_API_KEY for live research.
          </div>
        )}
        <div className="card research-box" role="form" aria-label="Start research">
          <label htmlFor="q"><strong>What do you want to research?</strong></label>
          <textarea id="q" className="q" value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} />
          <div className="row">
            <label htmlFor="depth">Research depth:</label>
            <select id="depth" value={depth} onChange={(e) => setDepth(e.target.value as "standard" | "deep")}>
              <option value="standard">Standard</option>
              <option value="deep">Deep</option>
            </select>
            <label htmlFor="doc">Upload sources (PDF/TXT/MD):</label>
            <input id="doc" type="file" accept=".pdf,.txt,.md,.markdown" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <button className="primary" onClick={start} disabled={busy}>{busy ? "Starting…" : "Start Research"}</button>
          </div>
          {error && <p role="alert" style={{ color: "#9b1c1c" }}>{error}</p>}
        </div>
        <div className="feature-grid">
          {[
            ["Source-grounded answers", "Every finding links to verbatim evidence passages."],
            ["Evidence tracking", "Claims map to sources; nothing is generated from thin air."],
            ["Citation verification", "A separate pass rejects unsupported or overstated claims."],
            ["Conflict detection", "Disagreements are shown side-by-side, never hidden."]
          ].map(([t, d]) => (
            <div className="card" key={t}><strong>{t}</strong><p className="meta">{d}</p></div>
          ))}
        </div>
      </section>
    </>
  );
}
