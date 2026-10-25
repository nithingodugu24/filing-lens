import { useState } from "react";
import {
  AlertCircle,
  Check,
  FileText,
  LoaderCircle,
  Upload,
  X,
} from "lucide-react";
import { api, type Document } from "./api";
import { useDialog } from "./dialog";

function dates(year: number, quarter: string, annual: boolean) {
  if (annual)
    return { period_start: `${year}-04-01`, period_end: `${year + 1}-03-31` };
  const ranges: { [key: string]: [string, string] } = {
    Q1: [`${year}-04-01`, `${year}-06-30`],
    Q2: [`${year}-07-01`, `${year}-09-30`],
    Q3: [`${year}-10-01`, `${year}-12-31`],
    Q4: [`${year + 1}-01-01`, `${year + 1}-03-31`],
  };
  const [start, end] = ranges[quarter];
  return { period_start: start, period_end: end };
}
const niceDate = (date: string) =>
  new Date(date + "T00:00:00").toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

export function UploadModal({
  onClose,
  onDone,
  maxUploadMb,
  companies,
}: {
  onClose: () => void;
  onDone: (doc: Document) => Promise<void>;
  maxUploadMb: number;
  companies: string[];
}) {
  const [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [company, setCompany] = useState(""),
    [title, setTitle] = useState(""),
    [type, setType] = useState("annual_report");
  const [year, setYear] = useState(new Date().getFullYear() - 1),
    [quarter, setQuarter] = useState("Q1"),
    [custom, setCustom] = useState(false),
    [customStart, setStart] = useState(""),
    [customEnd, setEnd] = useState("");
  const [basis, setBasis] = useState("consolidated"),
    [currency, setCurrency] = useState("INR"),
    [units, setUnits] = useState(""),
    [published, setPublished] = useState(""),
    [url, setUrl] = useState("");
  const ref = useDialog<HTMLElement>(() => {
    if (!busy) onClose();
  });
  const reportDates = custom
    ? { period_start: customStart, period_end: customEnd }
    : dates(year, quarter, type === "annual_report");
  const oversized = !!file && file.size > maxUploadMb * 1024 * 1024;
  const invalidFile = !!file && !/\.pdf$/i.test(file.name);
  function chooseFile(selected: File | null) {
    setFile(selected);
    setError("");
    if (!selected) return;
    setTitle(
      selected.name
        .replace(/\.pdf$/i, "")
        .replace(/[_-]+/g, " ")
        .slice(0, 240),
    );
    if (!/\.pdf$/i.test(selected.name))
      setError("Choose a PDF file. Other file types are not supported.");
    else if (selected.size > maxUploadMb * 1024 * 1024)
      setError(
        `This PDF is ${(selected.size / (1024 * 1024)).toFixed(1)} MB. The upload limit is ${maxUploadMb} MB.`,
      );
    const match = selected.name.match(/(20\d{2})[-_ ]+(?:20)?(\d{2})/);
    if (match && Number(match[2]) === (Number(match[1]) + 1) % 100)
      setYear(Number(match[1]));
    const q = selected.name.match(/\bq([1-4])\b/i);
    if (q) {
      setQuarter("Q" + q[1]);
      setType("quarterly_results");
    } else if (/annual/i.test(selected.name)) setType("annual_report");
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || oversized || invalidFile) return;
    setError("");
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append(
        "metadata",
        JSON.stringify({
          company: company.trim(),
          title: title.trim() || file.name.replace(/\.pdf$/i, ""),
          document_type: type,
          ...reportDates,
          basis,
          currency,
          units: units || null,
          publication_date: published || null,
          source_url: url || null,
        }),
      );
      const result = await api<{ document: Document; duplicate: boolean }>(
        "/documents",
        { method: "POST", body: form },
      );
      if (result.duplicate) {
        setError(
          "This PDF has already been uploaded. Close this window and open it from My reports.",
        );
        return;
      }
      await onDone(result.document);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const fiscalYears = [
    ...new Set([
      year,
      ...Array.from({ length: 18 }, (_, i) => new Date().getFullYear() + 1 - i),
    ]),
  ].sort((a, b) => b - a);
  return (
    <div className="modal-overlay">
      <section
        className="upload-modal"
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label="Upload report"
      >
        <div className="modal-heading">
          <div>
            <h2>Upload a report</h2>
            <p>Add the PDF and tell us which company and period it covers.</p>
          </div>
          <button
            className="close-button"
            aria-label="Close upload"
            disabled={busy}
            onClick={onClose}
          >
            <X size={22} />
          </button>
        </div>
        {error && (
          <div className="error" role="alert">
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}
        <form onSubmit={(e) => void submit(e)}>
          <fieldset disabled={busy}>
            <label
              className={"file-drop" + (file ? " has-file" : "")}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                chooseFile(e.dataTransfer.files[0] || null);
              }}
            >
              {file ? <FileText size={27} /> : <Upload size={27} />}
              <strong>
                {file ? file.name : "Choose a PDF or drag it here"}
              </strong>
              <span>
                {file
                  ? `${(file.size / (1024 * 1024)).toFixed(1)} MB selected`
                  : `PDF files up to ${maxUploadMb} MB`}
              </span>
              <input
                aria-label="PDF file"
                type="file"
                accept="application/pdf,.pdf"
                required
                onChange={(e) => chooseFile(e.target.files?.[0] || null)}
              />
            </label>
            <div className="form-grid">
              <label className="wide">
                Company name
                <input
                  aria-label="Company name"
                  required
                  maxLength={100}
                  list="company-names"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="For example, TCS or Infosys"
                  autoComplete="organization"
                />
                <datalist id="company-names">
                  {companies.map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
              </label>
              <label>
                Report type
                <select
                  aria-label="Report type"
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                >
                  <option value="annual_report">Annual report</option>
                  <option value="quarterly_results">Quarterly results</option>
                  <option value="presentation">Investor presentation</option>
                  <option value="transcript">Earnings call transcript</option>
                </select>
              </label>
              <label>
                Financial year
                <select
                  aria-label="Financial year"
                  value={year}
                  onChange={(e) => {
                    setYear(Number(e.target.value));
                    setCustom(false);
                  }}
                >
                  {fiscalYears.map((y) => (
                    <option key={y} value={y}>
                      {y}–{String(y + 1).slice(-2)}
                    </option>
                  ))}
                </select>
              </label>
              {type !== "annual_report" && (
                <label className="wide">
                  Quarter
                  <select
                    aria-label="Quarter"
                    value={quarter}
                    onChange={(e) => {
                      setQuarter(e.target.value);
                      setCustom(false);
                    }}
                  >
                    <option value="Q1">Q1 · April to June</option>
                    <option value="Q2">Q2 · July to September</option>
                    <option value="Q3">Q3 · October to December</option>
                    <option value="Q4">Q4 · January to March</option>
                  </select>
                </label>
              )}
              <div className="period-summary wide">
                <span>Reporting dates</span>
                <strong>
                  {reportDates.period_start && reportDates.period_end
                    ? `${niceDate(reportDates.period_start)} – ${niceDate(reportDates.period_end)}`
                    : "Choose the report dates below"}
                </strong>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={custom}
                    onChange={(e) => {
                      setCustom(e.target.checked);
                      setStart(reportDates.period_start);
                      setEnd(reportDates.period_end);
                    }}
                  />
                  Use different dates
                </label>
              </div>
              {custom && (
                <>
                  <label>
                    Period start
                    <input
                      aria-label="Period start"
                      type="date"
                      required
                      value={customStart}
                      onChange={(e) => setStart(e.target.value)}
                    />
                  </label>
                  <label>
                    Period end
                    <input
                      aria-label="Period end"
                      type="date"
                      min={customStart}
                      required
                      value={customEnd}
                      onChange={(e) => setEnd(e.target.value)}
                    />
                  </label>
                </>
              )}
              <label className="wide">
                Which figures does the report contain?
                <select
                  value={basis}
                  onChange={(e) => setBasis(e.target.value)}
                >
                  <option value="consolidated">
                    Entire company group (consolidated)
                  </option>
                  <option value="standalone">
                    Parent company only (standalone)
                  </option>
                </select>
              </label>
            </div>
            <details className="optional-details">
              <summary>Optional details</summary>
              <p>Add these if you know them. You can leave them blank.</p>
              <div className="form-grid">
                <label className="wide">
                  Report name
                  <input
                    aria-label="Report name"
                    maxLength={240}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </label>
                <label>
                  Publication date
                  <input
                    type="date"
                    value={published}
                    onChange={(e) => setPublished(e.target.value)}
                  />
                </label>
                <label>
                  Currency
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                  >
                    {["INR", "USD", "EUR", "GBP"].map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Units shown in report
                  <select
                    value={units}
                    onChange={(e) => setUnits(e.target.value)}
                  >
                    <option value="">Not sure</option>
                    {["unit", "lakh", "crore", "million", "billion"].map(
                      (u) => (
                        <option key={u}>{u}</option>
                      ),
                    )}
                  </select>
                </label>
                <label className="wide">
                  Official source link
                  <input
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://…"
                  />
                </label>
              </div>
            </details>
          </fieldset>
          <div className="upload-help">
            <Check size={16} />
            The PDF must contain selectable text. Scanned pages need text
            recognition first.
          </div>
          <div className="modal-actions">
            <button
              className="button secondary"
              type="button"
              disabled={busy}
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={busy || !file || oversized || invalidFile}
            >
              {busy ? (
                <LoaderCircle size={18} className="spin" />
              ) : (
                <Upload size={18} />
              )}{" "}
              {busy ? "Uploading…" : "Upload report"}
            </button>
          </div>
          {busy && (
            <p className="footnote">
              Keep this window open while the PDF uploads. Processing will
              continue in My reports.
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
