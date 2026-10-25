import { LoaderCircle } from "lucide-react";
import { useEffect, useRef } from "react";
import { apiFetch, type Answer } from "./api";

export type ProgressEvent = {
  type: "status" | "delta" | "draft";
  message?: string;
  text?: string;
};
export interface AnswerProgress {
  text: string;
  message: string;
}
export const initialProgress: AnswerProgress = {
  text: "",
  message: "Finding source passages…",
};
export function updateProgress(
  current: AnswerProgress,
  event: ProgressEvent,
): AnswerProgress {
  if (event.type === "status")
    return { ...current, message: event.message || current.message };
  return {
    ...current,
    text:
      event.type === "delta"
        ? current.text + (event.text || "")
        : event.text || "",
  };
}

export async function streamAnswer(
  path: string,
  data: unknown,
  onEvent: (event: ProgressEvent) => void,
  signal: AbortSignal,
): Promise<Answer> {
  const response = await apiFetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(data),
    signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "The answer could not start. Please try again.",
    );
  }
  // Older deployments and controlled test responses may still return complete JSON.
  if (!response.headers.get("content-type")?.includes("text/event-stream"))
    return response.json();
  if (!response.body)
    throw new Error("Streaming is unavailable in this browser.");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer = (buffer + decoder.decode(value, { stream: !done })).replace(
        /\r\n/g,
        "\n",
      );
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const type = block
          .split("\n")
          .find((l) => l.startsWith("event:"))
          ?.slice(6)
          .trim();
        const raw = block
          .split("\n")
          .filter((l) => l.startsWith("data:"))
          .map((l) => l.slice(5).trimStart())
          .join("\n");
        if (!raw) continue;
        const payload = JSON.parse(raw);
        if (type === "error")
          throw new Error(payload.message || "The answer was interrupted.");
        if (type === "done") return payload as Answer;
        if (type === "status" || type === "delta" || type === "draft")
          onEvent({ type, ...payload });
      }
      if (done)
        throw new Error(
          "The connection stopped before the answer finished. Please try again.",
        );
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function StreamingAnswer({
  progress,
  onStop,
}: {
  progress: AnswerProgress;
  onStop: () => void;
}) {
  const panel = useRef<HTMLElement>(null),
    shown = useRef(false);
  useEffect(() => {
    if (progress.text && !shown.current) {
      shown.current = true;
      panel.current?.scrollIntoView({ block: "start" });
    }
  }, [progress.text]);
  return (
    <section
      ref={panel}
      className="streaming-answer"
      aria-label="Answer in progress"
      aria-busy="true"
    >
      <div className="section-title">
        <span role="status">
          <LoaderCircle size={17} className="spin" /> {progress.message}
        </span>
        <button className="text-button" onClick={onStop}>
          Stop answer
        </button>
      </div>
      {progress.text && (
        <>
          <small>Draft · source checks pending</small>
          <p className="streaming-text">
            {progress.text}
            <span className="streaming-cursor" aria-hidden="true">
              ▍
            </span>
          </p>
        </>
      )}
    </section>
  );
}
