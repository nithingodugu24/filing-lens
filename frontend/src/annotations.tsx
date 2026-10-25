import { useEffect, useState } from "react";
import { api, post } from "./api";
type Note = {
  id: string;
  page_index: number;
  selected_text: string;
  note: string;
};
export function Annotations({
  documentId,
  pageIndex,
  selectedText,
  onPage,
}: {
  documentId: string;
  pageIndex: number;
  selectedText: string;
  onPage: (p: number, quote: string) => void;
}) {
  const [notes, setNotes] = useState<Note[]>([]),
    [note, setNote] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const load = () =>
    api<Note[]>(`/documents/${documentId}/annotations`)
      .then(setNotes)
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
  }, [documentId]);
  return (
    <section className="annotations">
      <h3>Saved notes</h3>
      <p>Select text in the report, then add a note.</p>
      {selectedText && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await post(`/documents/${documentId}/annotations`, {
                page_index: pageIndex,
                selected_text: selectedText,
                note,
              });
              setNote("");
              await load();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <blockquote>
            {selectedText.slice(0, 250)}
            {selectedText.length > 250 ? "…" : ""}
          </blockquote>
          <label>
            Your note
            <textarea
              required
              maxLength={2000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <button className="button primary" disabled={busy || !note.trim()}>
            {busy ? "Saving…" : "Save note"}
          </button>
        </form>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!notes.length && <p>No notes saved for this report.</p>}
      {notes.map((n) => (
        <article className="note-card" key={n.id}>
          <button
            className="citation"
            onClick={() => onPage(n.page_index, n.selected_text)}
          >
            ● Page {n.page_index + 1}
          </button>
          <blockquote>{n.selected_text}</blockquote>
          <p>{n.note}</p>
          <button
            className="text-button"
            onClick={async () => {
              try {
                await api(`/annotations/${n.id}`, { method: "DELETE" });
                await load();
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Delete note
          </button>
        </article>
      ))}
    </section>
  );
}
