import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, Thumbnail, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import { apiFetch } from "./api";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();
const escapeHtml = (text: string) =>
  text.replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
import { highlightRange } from "./text-highlights";
export function PdfReader({
  documentId,
  pageIndex,
  onPage,
  quote,
}: {
  documentId: string;
  pageIndex: number;
  onPage: (p: number) => void;
  quote: string;
}) {
  const [bytes, setBytes] = useState<Uint8Array | null>(null),
    [url, setUrl] = useState(""),
    [error, setError] = useState(""),
    [pages, setPages] = useState(0),
    [zoom, setZoom] = useState(1),
    [thumbs, setThumbs] = useState(false),
    [items, setItems] = useState<string[]>([]),
    [width, setWidth] = useState(600);
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    let blobUrl = "";
    setBytes(null);
    setError("");
    apiFetch(`/documents/${documentId}/file`)
      .then(async (r) => {
        if (!r.ok) throw new Error("Could not open this PDF");
        const buffer = await r.arrayBuffer();
        if (active) {
          setBytes(new Uint8Array(buffer));
          blobUrl = URL.createObjectURL(
            new Blob([buffer], { type: "application/pdf" }),
          );
          setUrl(blobUrl);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [documentId]);
  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(200, entries[0].contentRect.width - 32)),
    );
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => setItems([]), [pageIndex]);
  const file = useMemo(() => (bytes ? { data: bytes } : null), [bytes]);
  const range = highlightRange(items.join(" "), quote);
  const offsets = items.map((_, i) =>
    items.slice(0, i).reduce((n, s) => n + s.length + 1, 0),
  );
  function renderer({ str, itemIndex }: { str: string; itemIndex: number }) {
    const start = offsets[itemIndex] ?? 0;
    if (!range || range[1] <= start || range[0] >= start + str.length)
      return escapeHtml(str);
    const a = Math.max(0, range[0] - start),
      b = Math.min(str.length, range[1] - start);
    return (
      escapeHtml(str.slice(0, a)) +
      "<mark>" +
      escapeHtml(str.slice(a, b)) +
      "</mark>" +
      escapeHtml(str.slice(b))
    );
  }
  return (
    <div className="pdf-reader" ref={container}>
      <div className="pdf-toolbar">
        <button
          onClick={() => onPage(Math.max(0, pageIndex - 1))}
          disabled={!pageIndex}
        >
          Previous
        </button>
        <span>
          Page {pageIndex + 1}
          {pages ? ` / ${pages}` : ""}
        </span>
        <button
          onClick={() => onPage(pageIndex + 1)}
          disabled={!pages || pageIndex >= pages - 1}
        >
          Next
        </button>
        <button
          aria-label="Zoom out"
          onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))}
        >
          −
        </button>
        <button aria-label="Fit width" onClick={() => setZoom(1)}>
          Fit width
        </button>
        <button
          aria-label="Zoom in"
          onClick={() => setZoom((z) => Math.min(2, z + 0.2))}
        >
          +
        </button>
        <button onClick={() => setThumbs(!thumbs)}>
          {thumbs ? "Hide" : "Show"} pages
        </button>
      </div>
      {quote && (
        <p className="highlight-badge">
          {range
            ? "Highlighted text"
            : "Looking for the quoted text on this page"}
        </p>
      )}
      {error ? (
        <>
          <p>{error}. Showing the standard viewer.</p>
          {url && (
            <iframe
              title={`PDF page ${pageIndex + 1}`}
              src={`${url}#page=${pageIndex + 1}`}
            />
          )}
        </>
      ) : file ? (
        <Document
          suspense={false}
          file={file}
          onLoadSuccess={({ numPages }) => setPages(numPages)}
          onLoadError={() =>
            setError("The enhanced PDF viewer could not load this file")
          }
          loading={<p>Opening PDF…</p>}
        >
          <div className="pdf-layout">
            {thumbs && (
              <div className="pdf-thumbnails">
                {Array.from(
                  { length: Math.min(20, pages - pageIndex) },
                  (_, i) => pageIndex + i,
                ).map((p) => (
                  <button
                    aria-label={`Go to page ${p + 1}`}
                    key={p}
                    onClick={() => onPage(p)}
                  >
                    <Thumbnail pageNumber={p + 1} width={80} />
                    <span>{p + 1}</span>
                  </button>
                ))}
                <small>
                  Shows the current and next 19 pages. Use page navigation to
                  browse further.
                </small>
              </div>
            )}
            <div className="pdf-canvas">
              <Page
                suspense={false}
                pageNumber={pageIndex + 1}
                width={width * (thumbs ? 0.72 : 1) * zoom}
                customTextRenderer={renderer}
                onGetTextSuccess={(content) =>
                  setItems(
                    content.items.map((item) =>
                      "str" in item ? item.str : "",
                    ),
                  )
                }
                renderAnnotationLayer={false}
                loading={<p>Rendering page…</p>}
              />
            </div>
          </div>
        </Document>
      ) : (
        <p>Loading PDF…</p>
      )}
    </div>
  );
}
