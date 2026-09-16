"use client";
import { useEffect, useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function HumanEvalPage() {
  const [tasks, setTasks] = useState<{claim_id:string; claim_text:string; evidence:{quote:string; source_title:string}[]}[]>([]);
  const [label, setLabel] = useState("supported");
  const [msg, setMsg] = useState("");
  const [summary, setSummary] = useState<Record<string,unknown>|null>(null);
  const [cal, setCal] = useState<Record<string,unknown>|null>(null);
  const [selected, setSelected] = useState<string|null>(null);
  const sel = tasks.find(t=>t.claim_id===selected);
  useEffect(()=>{
    fetch(`${API}/api/eval/human/tasks?limit=10`).then(r=>r.json()).then(d=>setTasks(d.tasks||[])).catch(()=>{});
    fetch(`${API}/api/eval/human/summary`).then(r=>r.json()).then(setSummary).catch(()=>{});
    fetch(`${API}/api/eval/human/calibration`).then(r=>r.json()).then(setCal).catch(()=>{});
  },[]);
  async function submit(){
    if(!sel) return;
    const res = await fetch(`${API}/api/eval/human/labels`, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({claim_id: sel.claim_id, label, notes: ""})});
    if(res.ok){ setMsg("Label saved"); fetch(`${API}/api/eval/human/summary`).then(r=>r.json()).then(setSummary).catch(()=>{}); fetch(`${API}/api/eval/human/calibration`).then(r=>r.json()).then(setCal).catch(()=>{});}
    else setMsg("Failed: "+await res.text());
  }
  return (
    <section style={{padding:"24px 0 60px"}}>
      <h1 style={{fontFamily:"Georgia, serif"}}>Human Evaluation (Blind)</h1>
      <p className="meta">Judge claim support from evidence only — system confidence is hidden to avoid bias. Labels are stored separately from production data.</p>
      <div className="grid2">
        <div className="card">
          <h2>Tasks</h2>
          {tasks.map(t=>(
            <div key={t.claim_id} style={{border: selected===t.claim_id ? "2px solid #1a5632" : "1px solid #e6e2da", padding:8, margin:"8px 0", borderRadius:8}}>
              <button className="ghost" onClick={()=>setSelected(t.claim_id)} style={{textAlign:"left", width:"100%"}}>{t.claim_text.slice(0,120)}</button>
              {selected===t.claim_id && <div style={{marginTop:8}}>
                {t.evidence.map((e,i)=><blockquote key={i}>“{e.quote}” — <span className="meta">{e.source_title}</span></blockquote>)}
                <div className="row">
                  <select value={label} onChange={e=>setLabel(e.target.value)}>
                    <option value="supported">Supported</option>
                    <option value="partially_supported">Partially supported</option>
                    <option value="unsupported">Unsupported</option>
                    <option value="contradicted">Contradicted</option>
                  </select>
                  <button className="primary" onClick={submit}>Submit label</button>
                </div>
                {msg && <p className="meta">{msg}</p>}
                <p className="meta"><strong>Instructions:</strong> SUPPORTED = evidence directly supports claim. PARTIALLY = only part of claim supported. UNSUPPORTED = no support. CONTRADICTED = evidence conflicts.</p>
              </div>}
            </div>
          ))}
        </div>
        <div className="card">
          <h2>Summary</h2>
          <pre style={{whiteSpace:"pre-wrap", fontSize:12}}>{summary ? JSON.stringify(summary, null, 2) : "Loading…"}</pre>
          <h2>Calibration</h2>
          <pre style={{whiteSpace:"pre-wrap", fontSize:12}}>{cal ? JSON.stringify(cal, null, 2) : "Loading…"}</pre>
          <p className="meta">{cal && (cal as {status:string}).status==="unavailable" ? "Calibration needs ≥5 labels with claim confidence — honestly reported as unavailable until then." : ""}</p>
        </div>
      </div>
    </section>
  );
}
