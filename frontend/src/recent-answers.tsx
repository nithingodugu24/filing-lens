import { useEffect, useState } from "react";
import { api, type Answer } from "./api";

export function RecentAnswers({
  documentId,
  latestRun,
  onOpen,
}: {
  documentId: string;
  latestRun?: string;
  onOpen: (question: string, answer: Answer) => void;
}) {
  const [items, setItems] = useState<
      { id: string; question: string; created_at: string; response: Answer }[]
    >([]),
    [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    void api<typeof items>(
      `/history${documentId ? `?document_id=${documentId}` : ""}`,
    )
      .then((r) => {
        if (!cancelled) setItems(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, latestRun]);
  if (!items.length && !error) return null;
  return (
    <details className="recent-answers">
      <summary>Recent answers ({items.length})</summary>
      {error && <p role="alert">{error}</p>}
      {items.map((item) => (
        <div key={item.id}>
          <button onClick={() => onOpen(item.question, item.response)}>
            {item.question}
            <small>
              {new Date(item.created_at).toLocaleDateString("en-IN")}
            </small>
          </button>
          <button
            className="text-button"
            aria-label={`Remove saved answer: ${item.question}`}
            onClick={() =>
              void api(`/history/${item.id}`, { method: "DELETE" })
                .then(() => setItems(items.filter((i) => i.id !== item.id)))
                .catch((e) => setError(e.message))
            }
          >
            Remove
          </button>
        </div>
      ))}
    </details>
  );
}
