"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [question, setQuestion] = useState("What are the environmental impacts of desalination?");
  const [depth, setDepth] = useState<"standard" | "deep">("standard");
  const [mode, setMode] = useState<"web" | "private" | "hybrid">("web");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mock, setMock] = useState<boolean | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxSources, setMaxSources] = useState(12);
  const [maxRounds, setMaxRounds] = useState(2);
  const [strictness, setStrictness] = useState<"lenient" | "standard" | "strict">("standard");

  useEffect(() => {
    api.health().then((h) => setMock(h.mock_mode)).catch(() => setMock(null));
  }, []);

  async function start() {
    if (question.trim().length < 5) { setError("Please enter a research question."); return; }
    if (mode !== "web" && files.length === 0) { setError("Private/hybrid mode needs at least one uploaded document."); return; }
    setBusy(true); setError("");
    try {
      const document_ids: string[] = [];
      for (const f of files) {
        const u = await api.upload(f);
        document_ids.push(u.document_id);
      }
      const r = await api.createResearch(question.trim(), {
        depth, mode, document_ids,
        max_sources: maxSources, max_rounds: maxRounds, strictness
      });
      router.push(`/research/${r.run_id}`);
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
        {mock === true && mode === "web" && (
          <div className="mock-banner" role="status">
            Development/mock mode is active: results use labeled fixture sources. Configure SEARCH_API_KEY + LLM_API_KEY for live research.
          </div>
        )}
        <div className="card research-box" role="form" aria-label="Start research">
          <label htmlFor="q"><strong>What do you want to research?</strong></label>
          <textarea id="q" className="q" value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} />
          <div className="row" role="radiogroup" aria-label="Research mode">
            <span>Research mode:</span>
            {(["web", "private", "hybrid"] as const).map((m) => (
              <label key={m} style={{ display: "flex", gap: 4, alignItems: "center", fontSize: 14 }}>
                <input type="radio" name="mode" checked={mode === m} onChange={() => setMode(m)} />
                {m === "web" ? "Web" : m === "private" ? "Private documents" : "Hybrid"}
              </label>
            ))}
            <label htmlFor="depth">Research depth:</label>
            <select id="depth" value={depth} onChange={(e) => setDepth(e.target.value as "standard" | "deep")}>
              <option value="standard">Standard</option>
              <option value="deep">Deep</option>
            </select>
          </div>
          <div className="row">
            <label htmlFor="doc">Upload sources (PDF/TXT/MD):</label>
            <input id="doc" type="file" accept=".pdf,.txt,.md,.markdown" multiple
              onChange={(e) => setFiles(Array.from(e.target.files || []))} />
            {files.length > 0 && <span className="meta">{files.length} file(s) selected</span>}
          </div>
          <div>
            <button className="ghost" aria-expanded={showAdvanced} onClick={() => setShowAdvanced(!showAdvanced)}>
              {showAdvanced ? "Hide advanced settings" : "Advanced settings"}
            </button>
            {showAdvanced && (
              <div className="row" style={{ marginTop: 8 }}>
                <label>Max sources: <input type="number" min={1} max={30} value={maxSources} onChange={(e) => setMaxSources(Number(e.target.value))} style={{ width: 60 }} /></label>
                <label>Research rounds: <input type="number" min={1} max={5} value={maxRounds} onChange={(e) => setMaxRounds(Number(e.target.value))} style={{ width: 60 }} /></label>
                <label>Evidence strictness:
                  <select value={strictness} onChange={(e) => setStrictness(e.target.value as "lenient" | "standard" | "strict")}>
                    <option value="lenient">Lenient</option>
                    <option value="standard">Standard</option>
                    <option value="strict">Strict</option>
                  </select>
                </label>
              </div>
            )}
          </div>
          <div className="row">
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
