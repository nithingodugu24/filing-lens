import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  ExternalLink,
  PanelRightClose,
  ShieldCheck,
} from "lucide-react";
import { api, apiFetch, type Evidence } from "./api";
import { useDialog } from "./dialog";
import { lazy, Suspense } from "react";
import { HighlightText } from "./text-highlights";
const PdfReader = lazy(() =>
  import("./pdf-reader").then((m) => ({ default: m.PdfReader })),
);
import { Annotations } from "./annotations";
import { Sentiment } from "./sentiment";
import { EntityText, type PageEntity } from "./entity-text";
type PageData = {
  text: string;
  printed_label: string | null;
  tables: { id: string; cells: string[][] }[];
};
export function EvidencePanel({
  evidence: e,
  onClose,
}: {
  evidence: Evidence;
  onClose: () => void;
}) {
  const [pageIndex, setPageIndex] = useState(e.page_index),
    [quote, setQuote] = useState(e.highlightText ?? ""),
    [page, setPage] = useState<PageData | null>(null),
    [tab, setTab] = useState("text"),
    [error, setError] = useState(""),
    [selectedText, setSelectedText] = useState("");
  const dialog = useDialog<HTMLElement>(onClose),
    reader = useRef<HTMLDivElement>(null);
  const [entities, setEntities] = useState<PageEntity[]>([]),
    [showEntities, setShowEntities] = useState(false);
  useEffect(() => {
    let active = true;
    setEntities([]);
    api<PageEntity[]>(
      `/documents/${e.document_id}/entities?page_index=${pageIndex}`,
    )
      .then((rows) => {
        if (active) setEntities(rows);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [e.document_id, pageIndex]);
  useEffect(() => {
    setPageIndex(e.page_index);
    setQuote(e.highlightText ?? "");
    setSelectedText("");
  }, [e]);
  useEffect(() => {
    let active = true;
    setPage(null);
    setError("");
    api<PageData>(`/documents/${e.document_id}/pages/${pageIndex}`)
      .then((p) => {
        if (active) setPage(p);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [e.document_id, pageIndex]);
  function go(p: number, text = "") {
    setPageIndex(p);
    setQuote(text);
    setSelectedText("");
    setTab("text");
  }
  async function openPdf() {
    const popup = window.open("", "_blank");
    try {
      const response = await apiFetch(`/documents/${e.document_id}/file`);
      if (!response.ok) throw new Error("Could not open the PDF");
      const url = URL.createObjectURL(await response.blob());
      if (popup) popup.location.href = `${url}#page=${pageIndex + 1}`;
      setTimeout(() => URL.revokeObjectURL(url), 120000);
    } catch (err) {
      popup?.close();
      setError((err as Error).message);
    }
  }
  return (
    <div className="panel-overlay" onClick={onClose}>
      <aside
        ref={dialog}
        className="evidence-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Evidence reader"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="panel-heading">
          <span>
            <BookOpen size={18} /> Source page
          </span>
          <button aria-label="Close evidence reader" onClick={onClose}>
            <PanelRightClose size={21} />
          </button>
        </div>
        <div className="panel-doc">
          <span className="eyebrow">
            {e.synthetic
              ? "SAMPLE REPORT · MADE-UP DATA"
              : "YOUR UPLOADED REPORT"}
          </span>
          <h2>{e.title}</h2>
          <div className="page-badge">
            PDF page {pageIndex + 1}
            <span>
              Printed label:{" "}
              {page?.printed_label || e.printed_label || "not available"}
            </span>
          </div>
        </div>
        <div className="reader-tabs">
          {[
            ["text", "Read text"],
            ["pdf", "View PDF"],
            ["notes", "Notes"],
            ["sentiment", "Sentiment"],
          ].map(([id, label]) => (
            <button
              key={id}
              className={tab === id ? "selected" : ""}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
          <a
            href={`/api/documents/${e.document_id}/file#page=${pageIndex + 1}`}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => {
              if (localStorage.getItem("filinglens-token")) {
                event.preventDefault();
                void openPdf();
              }
            }}
          >
            Open PDF <ExternalLink size={13} />
          </a>
        </div>
        {quote && (
          <div className="quote-toolbar">
            <span className="highlight-badge">Highlighted text</span>
            <button className="text-button" onClick={() => setQuote("")}>
              Clear highlights
            </button>
          </div>
        )}
        {selectedText && tab !== "notes" && (
          <button className="save-note-button" onClick={() => setTab("notes")}>
            Save note for selected text
          </button>
        )}
        <div
          className="reader-scroll"
          ref={reader}
          onMouseUp={() => {
            const selection = window.getSelection();
            if (
              selection?.anchorNode &&
              reader.current?.contains(selection.anchorNode) &&
              !selection.anchorNode.parentElement?.closest(
                ".annotations,.sentiment-panel",
              )
            ) {
              const text = selection.toString().trim();
              if (text.length >= 3 && text.length <= 4000)
                setSelectedText(text);
            }
          }}
        >
          {tab === "notes" ? (
            <Annotations
              documentId={e.document_id}
              pageIndex={pageIndex}
              selectedText={selectedText}
              onPage={go}
            />
          ) : tab === "sentiment" ? (
            <Sentiment documentId={e.document_id} onPage={go} />
          ) : error ? (
            <div className="error" role="alert">
              {error}
            </div>
          ) : tab === "pdf" ? (
            <Suspense
              fallback={<div className="skeleton">Opening PDF viewer…</div>}
            >
              <PdfReader
                documentId={e.document_id}
                pageIndex={pageIndex}
                quote={quote}
                onPage={(p) => {
                  setPageIndex(p);
                  setQuote("");
                  setSelectedText("");
                }}
              />
            </Suspense>
          ) : (
            <div className="reader-content">
              {page ? (
                <>
                  <div className="reader-text">
                    {showEntities ? (
                      <EntityText
                        text={page.text}
                        quote={quote}
                        entities={entities}
                      />
                    ) : (
                      <HighlightText text={page.text} quote={quote} />
                    )}
                  </div>
                  {entities.length > 0 && (
                    <label className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={showEntities}
                        onChange={(event) =>
                          setShowEntities(event.target.checked)
                        }
                      />
                      Underline detected names and figures
                    </label>
                  )}
                  {page.tables.length > 0 && (
                    <>
                      <h3>Tables found on this page</h3>
                      {page.tables.map((t) => (
                        <div className="table-wrap" key={t.id}>
                          <table className="extracted-table">
                            <tbody>
                              {t.cells.map((row, i) => (
                                <tr key={i}>
                                  {row.map((cell, j) => (
                                    <td key={j}>{cell}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ))}
                    </>
                  )}
                </>
              ) : (
                <p role="status">Loading page…</p>
              )}
              {e.source_url && (
                <a
                  className="source-link"
                  href={e.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Original source <ExternalLink size={14} />
                </a>
              )}
            </div>
          )}
        </div>
        <div className="reader-footer">
          <ShieldCheck size={15} /> PDF page numbers are 1-based here. Printed
          labels may differ.
        </div>
      </aside>
    </div>
  );
}
