import { useEffect, useRef, useState } from "react";
import { type Answer, type Evidence } from "./api";
import {
  streamAnswer,
  StreamingAnswer,
  initialProgress,
  updateProgress,
} from "./answer-stream";
import { MetricCard } from "./metric-card";

export function Confidence({ value }: { value?: number | null }) {
  if (value == null) return null;
  return (
    <span
      className={`confidence ${value >= 0.8 ? "high" : value >= 0.5 ? "moderate" : "low"}`}
    >
      {value >= 0.8
        ? "High confidence"
        : value >= 0.5
          ? "Moderate confidence"
          : "Low confidence — verify sources"}{" "}
      <small>Model estimate · not independently verified</small>
    </span>
  );
}
export function Conversation({
  filters,
  mode,
  onEvidence,
}: {
  filters: Record<string, unknown>;
  mode: string;
  onEvidence: (e: Evidence) => void;
}) {
  const [session, setSession] = useState(() => crypto.randomUUID()),
    [turns, setTurns] = useState<{ question: string; answer: Answer }[]>([]),
    [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const controllerRef = useRef<AbortController | null>(null);
  const [progress, setProgress] = useState(initialProgress);
  useEffect(() => () => controllerRef.current?.abort(), []);
  function stop() {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setBusy(false);
    setProgress(initialProgress);
  }
  async function ask() {
    if (busy || question.trim().length < 3) return;
    setBusy(true);
    setError("");
    const controller = new AbortController();
    controllerRef.current = controller;
    setProgress(initialProgress);
    try {
      const answer = await streamAnswer(
        "/conversations",
        {
          session_id: session,
          question,
          filters,
          mode,
          k: 8,
        },
        (event) => {
          if (!controller.signal.aborted)
            setProgress((current) => updateProgress(current, event));
        },
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setTurns((t) => [...t, { question, answer }]);
      setQuestion("");
    } catch (e) {
      if (!controller.signal.aborted) setError((e as Error).message);
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setBusy(false);
        setProgress(initialProgress);
      }
    }
  }
  return (
    <section className="conversation">
      <div className="section-title">
        <h2>Conversation</h2>
        <button
          className="text-button"
          disabled={busy}
          onClick={() => {
            setSession(crypto.randomUUID());
            setTurns([]);
            setError("");
          }}
        >
          New conversation
        </button>
      </div>
      <p>
        Follow-up questions keep the recent context. Every answer still uses the
        reports selected above.
      </p>
      <div aria-live="polite">
        {turns.map((turn, i) => (
          <div className="chat-turn" key={i}>
            <div className="chat-user">{turn.question}</div>
            <div className="chat-answer">
              <Confidence value={turn.answer.confidence} />
              {turn.answer.summary && <p>{turn.answer.summary}</p>}
              <div className="metric-grid">
                {turn.answer.metric_answers?.map((m) => (
                  <MetricCard
                    key={m.fact_id}
                    metric={m}
                    evidence={turn.answer.evidence.find(
                      (e) => e.id === m.citation_id,
                    )}
                    onEvidence={onEvidence}
                  />
                ))}
              </div>
              {turn.answer.abstained ? (
                <p>{turn.answer.limitation}</p>
              ) : (
                turn.answer.claims.map((claim, j) => (
                  <article key={j}>
                    <p>{claim.text}</p>
                    <div className="citation-row">
                      {claim.citation_ids.map((id) => {
                        const e = turn.answer.evidence.find((e) => e.id === id);
                        return (
                          e && (
                            <button
                              className="citation"
                              key={id}
                              onClick={() =>
                                onEvidence({
                                  ...e,
                                  highlightText: claim.supporting_quote,
                                })
                              }
                            >
                              Open {e.company} · page {e.page_index + 1}
                            </button>
                          )
                        );
                      })}
                    </div>
                  </article>
                ))
              )}
              {turn.answer.calculations.map((c, j) => (
                <p key={j}>
                  <strong>
                    {c.company}: {c.result} {c.units}
                  </strong>{" "}
                  · {c.formula}
                </p>
              ))}
            </div>
          </div>
        ))}
      </div>
      {busy && <StreamingAnswer progress={progress} onStop={stop} />}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
      >
        <label>
          Ask a follow-up
          <textarea
            rows={3}
            maxLength={2000}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                void ask();
              }
            }}
            placeholder="For example, what affected operating margin?"
          />
        </label>
        <button
          className="button primary"
          disabled={busy || question.trim().length < 3}
        >
          {busy ? "Finding an answer…" : "Send question"}
        </button>
      </form>
    </section>
  );
}
