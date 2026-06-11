"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type Segment = { seq: number; speaker: string; text: string };
type RunEvent = {
  type: string;
  data: Record<string, unknown>;
  run_id: string;
};

const SPEAKER_LABEL: Record<string, string> = {
  assistant: "Ассистент",
  callee: "Собеседник",
  system: "Система",
};

// EPIC-002 live-call page: live transcript, status, Hang up, Whisper.
// Approve/Reject stays in Telegram; Take over is deferred to Stage 3.
export default function LiveCallPage() {
  const { id } = useParams<{ id: string }>();
  const [segments, setSegments] = useState<Segment[]>([]);
  const [callState, setCallState] = useState<string>("—");
  const [runStatus, setRunStatus] = useState<string>("—");
  const [connection, setConnection] = useState<"connecting" | "open" | "closed">("connecting");
  const [summary, setSummary] = useState<string | null>(null);
  const [whisper, setWhisper] = useState("");
  const [busy, setBusy] = useState(false);
  const [paused, setPaused] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    const source = new EventSource(`${API_BASE}/runs/${id}/events`);
    source.onopen = () => setConnection("open");
    source.onerror = () => setConnection("closed");

    const handle = (raw: MessageEvent) => {
      const event: RunEvent = JSON.parse(raw.data);
      if (event.type === "transcript_segment") {
        const d = event.data as { seq: number; speaker: string; text: string };
        setSegments((prev) =>
          prev.some((s) => s.seq === d.seq) ? prev : [...prev, d].sort((a, b) => a.seq - b.seq)
        );
      } else if (event.type === "status_changed") {
        setRunStatus(String(event.data.status ?? "—"));
        if (event.data.call_state) {
          setCallState(String(event.data.call_state));
          setPaused(event.data.call_state === "paused");
        }
      } else if (event.type === "approval_requested") {
        setCallState("ожидает подтверждения в Telegram");
      } else if (event.type === "run_completed") {
        setRunStatus("completed");
        setCallState("завершён");
        setSummary(String(event.data.result_summary ?? ""));
        source.close();
      } else if (event.type === "run_failed") {
        setRunStatus("failed");
        setCallState("ошибка");
        setSummary(String(event.data.failure_reason ?? ""));
        source.close();
      }
    };
    for (const type of [
      "status_changed",
      "transcript_segment",
      "approval_requested",
      "approval_resolved",
      "run_completed",
      "run_failed",
    ]) {
      source.addEventListener(type, handle);
    }
    return () => source.close();
  }, [id]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [segments]);

  const hangUp = useCallback(async () => {
    if (!id || busy) return;
    setBusy(true);
    try {
      await fetch(`${API_BASE}/runs/${id}/hangup`, { method: "POST" });
    } finally {
      setBusy(false);
    }
  }, [id, busy]);

  const sendWhisper = useCallback(async () => {
    if (!id || !whisper.trim() || busy) return;
    setBusy(true);
    try {
      await fetch(`${API_BASE}/runs/${id}/whisper`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: whisper.trim() }),
      });
      setWhisper("");
    } finally {
      setBusy(false);
    }
  }, [id, whisper, busy]);

  const togglePause = useCallback(async () => {
    if (!id || busy) return;
    setBusy(true);
    try {
      await fetch(`${API_BASE}/runs/${id}/${paused ? "resume" : "pause"}`, { method: "POST" });
      setPaused(!paused);
    } finally {
      setBusy(false);
    }
  }, [id, paused, busy]);

  const active = runStatus === "running" || runStatus === "waiting_approval";

  return (
    <main style={{ maxWidth: 720, margin: "0 auto" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1 style={{ fontSize: "1.2rem" }}>Звонок</h1>
        <div style={{ fontSize: "0.85rem", opacity: 0.8 }}>
          SSE: {connection} · статус: {runStatus} · этап: {callState}
        </div>
      </header>

      <div
        ref={logRef}
        style={{
          height: "50vh",
          overflowY: "auto",
          border: "1px solid #2a2f3a",
          borderRadius: 8,
          padding: "1rem",
          margin: "1rem 0",
          background: "#11151d",
        }}
      >
        {segments.length === 0 && <p style={{ opacity: 0.5 }}>Ожидание транскрипта…</p>}
        {segments.map((s) => (
          <p key={s.seq} style={{ margin: "0.4rem 0" }}>
            <strong style={{ color: s.speaker === "assistant" ? "#7aa2f7" : "#9ece6a" }}>
              {SPEAKER_LABEL[s.speaker] ?? s.speaker}:
            </strong>{" "}
            {s.text}
          </p>
        ))}
        {summary && (
          <p style={{ marginTop: "1rem", borderTop: "1px solid #2a2f3a", paddingTop: "1rem" }}>
            <strong>Итог:</strong> {summary}
          </p>
        )}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={whisper}
          onChange={(e) => setWhisper(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendWhisper()}
          placeholder="Подсказка ассистенту (whisper)…"
          disabled={!active || busy}
          style={{
            flex: 1,
            padding: "0.5rem 0.75rem",
            borderRadius: 6,
            border: "1px solid #2a2f3a",
            background: "#11151d",
            color: "inherit",
          }}
        />
        <button
          onClick={sendWhisper}
          disabled={!active || !whisper.trim() || busy}
          style={{ padding: "0.5rem 1rem", borderRadius: 6 }}
        >
          Отправить
        </button>
        <button
          onClick={togglePause}
          disabled={!active || busy}
          style={{
            padding: "0.5rem 1rem",
            borderRadius: 6,
            background: paused ? "#9ece6a" : "#e0af68",
            color: "#1a1b26",
            fontWeight: 600,
          }}
        >
          {paused ? "Продолжить" : "Пауза"}
        </button>
        <button
          onClick={hangUp}
          disabled={!active || busy}
          style={{
            padding: "0.5rem 1rem",
            borderRadius: 6,
            background: "#f7768e",
            color: "#1a1b26",
            fontWeight: 600,
          }}
        >
          Завершить звонок
        </button>
      </div>
    </main>
  );
}
