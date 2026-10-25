import { useState } from "react";
import { apiFetch, type Document } from "./api";
import { useDialog } from "./dialog";
import { X } from "lucide-react";
export async function downloadReport(
  ids: string[],
  format: string,
  includeQa: boolean,
  runId?: string,
) {
  const response = await apiFetch("/export/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_ids: ids,
      format,
      include_qa: includeQa,
      ...(runId ? { run_id: runId } : {}),
    }),
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.detail || "The report could not be exported.");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `filinglens-analysis.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
export function ExportModal({
  docs,
  onClose,
}: {
  docs: Document[];
  onClose: () => void;
}) {
  const dialog = useDialog<HTMLDivElement>(onClose),
    [selected, setSelected] = useState<string[]>([]),
    [format, setFormat] = useState("pdf"),
    [qa, setQa] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-label="Export analysis"
        className="upload-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2>Export analysis</h2>
          <button aria-label="Close export" onClick={onClose}>
            <X />
          </button>
        </div>
        <p>
          Select reports to include. Only source-checked financial figures are
          exported.
        </p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await downloadReport(selected, format, qa);
              onClose();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <fieldset>
            <legend>Reports</legend>
            {docs
              .filter((d) => d.status === "indexed")
              .map((d) => (
                <label className="checkbox-row" key={d.id}>
                  <input
                    type="checkbox"
                    checked={selected.includes(d.id)}
                    onChange={(e) =>
                      setSelected((s) =>
                        e.target.checked
                          ? [...s, d.id]
                          : s.filter((id) => id !== d.id),
                      )
                    }
                  />
                  {d.title}
                  {d.synthetic ? " · Sample" : ""}
                </label>
              ))}
          </fieldset>
          <label>
            Download format
            <select value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="pdf">PDF report</option>
              <option value="xlsx">Excel workbook</option>
              <option value="csv">CSV facts</option>
              <option value="md">Markdown report</option>
            </select>
          </label>
          {format !== "csv" && (
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={qa}
                onChange={(e) => setQa(e.target.checked)}
              />
              Include Q&amp;A history for these reports
            </label>
          )}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button
            className="button primary"
            disabled={busy || !selected.length}
          >
            {busy ? "Preparing download…" : "Generate & download"}
          </button>
        </form>
      </div>
    </div>
  );
}
