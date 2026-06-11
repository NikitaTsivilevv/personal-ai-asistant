"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type FeedLine = { ts: string; type: string; raw: string };

// Stage 1 stub: raw SSE feed of run events. The real live-call control page
// (transcript, hints, abort button) is built in EPIC-002.
export default function RunFeedPage() {
  const { id } = useParams<{ id: string }>();
  const [lines, setLines] = useState<FeedLine[]>([]);
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!id) return;
    const source = new EventSource(`${API_BASE}/runs/${id}/events`);
    sourceRef.current = source;
    source.onopen = () => setStatus("open");
    source.onerror = () => setStatus("closed");
    const push = (event: MessageEvent, type: string) =>
      setLines((prev) => [...prev, { ts: new Date().toLocaleTimeString(), type, raw: event.data }]);
    for (const type of [
      "status_changed",
      "transcript_segment",
      "approval_requested",
      "approval_resolved",
      "run_completed",
      "run_failed",
    ]) {
      source.addEventListener(type, (e) => push(e as MessageEvent, type));
    }
    return () => source.close();
  }, [id]);

  return (
    <main>
      <h1>Run {id}</h1>
      <p>SSE: {status}</p>
      <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
        {lines.map((l, i) => `[${l.ts}] ${l.type}\n${l.raw}\n\n`).join("")}
      </pre>
    </main>
  );
}
