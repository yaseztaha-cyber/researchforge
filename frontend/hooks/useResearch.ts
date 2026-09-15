"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export type Phase = "idle" | "running" | "done" | "failed";

export function useResearch(runId: string | null) {
  const [stage, setStage] = useState("queued");
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("queued");
  const [detail, setDetail] = useState("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!runId) return;
    setStatus("running");
    const poll = async () => {
      try {
        const p = await api.progress(runId);
        setStage(p.stage);
        setProgress(p.progress);
        setStatus(p.status);
        setDetail(p.detail);
        if (p.status === "completed" || p.status === "partial" || p.status === "failed") {
          if (timer.current) clearInterval(timer.current);
        }
      } catch {
        /* keep polling; backend may be starting */
      }
    };
    poll();
    timer.current = setInterval(poll, 1500);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [runId]);

  return { stage, progress, status, detail };
}
