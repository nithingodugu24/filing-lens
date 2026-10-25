import { useState } from "react";
import { post, type Answer, type Evidence } from "./api";

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
  async function ask() {
    if (busy || question.trim().length < 3) return;
    setBusy(true);
    setError("");
    try {
      const answer = await post<Answer>("/conversations", {
        session_id: session,
        question,
        filters,
        mode,
        k: 8,
      });
      setTurns((t) => [...t, { question, answer }]);
      setQuestion("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
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
