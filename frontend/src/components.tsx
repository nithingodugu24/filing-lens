import React, { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  ChartNoAxesCombined,
  Check,
  Clock3,
  FileText,
  FlaskConical,
  LoaderCircle,
  Search,
  ShieldCheck,
  Upload,
  X,
  ExternalLink,
  AlertCircle,
  PanelRightClose,
} from "lucide-react";
import {
  api,
  post,
  period,
  number,
  type Calculation,
  type Document,
  type Evidence,
  type Fact,
} from "./api";
export function DocumentTable({
  docs,
  onOpen,
  onRetry,
}: {
  docs: Document[];
  onOpen: (d: Document) => void;
  onRetry: (id: string) => void;
}) {
  return (
    <div className="table-wrap">
      <table className="document-table">
        <thead>
          <tr>
            <th>DOCUMENT</th>
            <th>COMPANY</th>
            <th>PERIOD</th>
            <th>STATUS</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              <td>
                <button
                  className="doc-title"
                  disabled={d.status !== "indexed"}
                  onClick={() => onOpen(d)}
                >
                  <span className="file-icon">
                    <FileText size={19} />
                  </span>
                  <span>
                    {d.title}
                    <small>
                      {d.document_type.replaceAll("_", " ")} ·{" "}
                      {d.synthetic ? "Synthetic demo" : d.basis} ·{" "}
                      {d.page_count} pages
                    </small>
                  </span>
                </button>
                {d.warning && (
                  <div className="document-warning">{d.warning}</div>
                )}
              </td>
              <td>
                <span className="table-company">{d.company}</span>
              </td>
              <td>{period(d.period_end)}</td>
              <td>
                <span className={`status ${d.status}`}>
                  {d.status === "indexed" ? (
                    <Check size={12} />
                  ) : d.status === "failed" ? (
                    <AlertCircle size={12} />
                  ) : (
                    <Clock3 size={12} />
                  )}{" "}
                  {d.status}
                </span>
              </td>
              <td>
                {d.status === "failed" ? (
                  <button className="text-button" onClick={() => onRetry(d.id)}>
                    Retry
                  </button>
                ) : (
                  <button
                    className="icon-button"
                    aria-label={`Open ${d.title}`}
                    disabled={d.status !== "indexed"}
                    onClick={() => onOpen(d)}
                  >
                    <ArrowUpRight size={17} />
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!docs.length && (
        <div className="table-empty">
          No documents match this scope. Adjust the filters or add a document.
        </div>
      )}
    </div>
  );
}
export function CalculationCard({
  calculation: c,
  onEvidence,
  evidence = [],
}: {
  calculation: Calculation;
  onEvidence: (e: Evidence) => void;
  evidence?: Evidence[];
}) {
  const sources =
    c.citations ||
    c.citation_ids
      ?.map((id) => evidence.find((e) => e.id === id))
      .filter((e): e is Evidence => !!e) ||
    [];
  return (
    <div className="calculation">
      <div className="calculation-title">
        <ChartNoAxesCombined size={17} />
        <strong>{c.company || "Metric comparison"}</strong>
        <span>Calculated in Python</span>
      </div>
      <div className="calculation-result">
        {number(c.result)}
        <span>{c.units}</span>
      </div>
      <code>{c.formula}</code>
      <div className="calculation-inputs">
        {c.input_values.map((v, i) => (
          <div key={i}>
            <small>
              {i === 0 ? "FIRST INPUT" : "SECOND INPUT"} · {v.period.fiscal}
            </small>
            <strong>
              {v.currency === "PCT" ? "" : v.currency + " "}
              {number(v.value)} {v.units}
            </strong>
            <span>
              {v.basis} · {v.revision}
            </span>
          </div>
        ))}
      </div>
      <details>
        <summary>Normalised inputs</summary>
        <pre>{JSON.stringify(c.normalised_inputs, null, 2)}</pre>
      </details>
      <div className="citation-row">
        {sources.map((e, i) => (
          <button key={i} className="citation" onClick={() => onEvidence(e)}>
            <FileText size={13} />
            {e.company} · PDF p. {e.page_index + 1}
            <ArrowUpRight size={12} />
          </button>
        ))}
      </div>
    </div>
  );
}
export function CompareView({
  facts,
  onEvidence,
  onError,
}: {
  facts: Fact[];
  onEvidence: (e: Evidence) => void;
  onError: (s: string) => void;
}) {
  const [metric, setMetric] = useState("revenue"),
    [first, setFirst] = useState(""),
    [second, setSecond] = useState(""),
    [operation, setOperation] = useState("percentage_change"),
    [result, setResult] = useState<Calculation | null>(null),
    [busy, setBusy] = useState(false);
  const eligible = facts
    .filter((f) => f.metric === metric && f.verified)
    .sort(
      (a, b) =>
        a.company.localeCompare(b.company) ||
        a.period_end.localeCompare(b.period_end),
    );
  const factKey = facts.map((f) => f.id).join(",");
  useEffect(() => {
    setFirst(eligible[0]?.id || "");
    setSecond(eligible[1]?.id || "");
    setResult(null);
  }, [metric, factKey]);
  async function calculate() {
    setBusy(true);
    setResult(null);
    try {
      setResult(
        await post<Calculation>("/compare", {
          fact_ids: [first, second],
          operation,
        }),
      );
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="compare-view">
      <div className="section-title">
        <h2>Compare verified financial facts</h2>
        <span>
          <ShieldCheck size={15} /> {eligible.length} reviewed facts in scope
        </span>
      </div>
      <div className="compare-builder">
        <div className="compare-controls">
          <label>
            Metric
            <select
              aria-label="Comparison metric"
              value={metric}
              onChange={(e) => {
                setMetric(e.target.value);
                setOperation(
                  e.target.value === "revenue"
                    ? "percentage_change"
                    : "percentage_points",
                );
              }}
            >
              <option value="revenue">Revenue</option>
              <option value="operating_margin">Operating margin</option>
            </select>
          </label>
          <label>
            Calculation
            <select
              aria-label="Calculation type"
              value={operation}
              onChange={(e) => {
                setOperation(e.target.value);
                setResult(null);
              }}
            >
              {metric === "revenue" ? (
                <>
                  <option value="percentage_change">
                    Percentage change (%)
                  </option>
                  <option value="difference">Absolute difference</option>
                </>
              ) : (
                <>
                  <option value="percentage_points">
                    Percentage-point change
                  </option>
                  <option value="basis_points">Basis-point change</option>
                </>
              )}
            </select>
          </label>
        </div>
        <div className="compare-pair">
          {[
            { label: "First disclosure", value: first, set: setFirst },
            { label: "Second disclosure", value: second, set: setSecond },
          ].map((s, i) => (
            <React.Fragment key={s.label}>
              {i === 1 && (
                <span className="pair-arrow">
                  <ArrowRight size={22} />
                </span>
              )}
              <label>
                {s.label}
                <select
                  aria-label={s.label}
                  value={s.value}
                  onChange={(e) => {
                    s.set(e.target.value);
                    setResult(null);
                  }}
                >
                  {!eligible.length && (
                    <option value="">No reviewed facts</option>
                  )}
                  {eligible.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.company} · {period(f.period_end)} · {number(f.value)}{" "}
                      {f.units} · {f.synthetic ? "synthetic" : f.basis}
                    </option>
                  ))}
                </select>
                <small>
                  {eligible.find((f) => f.id === s.value)?.basis ||
                    "Review extracted facts in the library first."}
                </small>
              </label>
            </React.Fragment>
          ))}
        </div>
        <button
          className="button primary"
          disabled={busy || !first || !second || first === second}
          onClick={() => void calculate()}
        >
          {busy ? (
            <LoaderCircle size={15} className="spin" />
          ) : (
            <ChartNoAxesCombined size={16} />
          )}
          Calculate comparison
        </button>
      </div>
      {result && (
        <CalculationCard calculation={result} onEvidence={onEvidence} />
      )}
      <div className="principle-note">
        <ShieldCheck size={21} />
        <div>
          <strong>Comparable inputs come first.</strong>
          <p>
            Currency, units, basis, reporting duration and revision status are
            checked. Cross-company comparisons require matching dates.
            Unreviewed facts stay out of calculations.
          </p>
        </div>
      </div>
      <div className="section-title">
        <h3>Facts available in this scope</h3>
        <span>Original values retained</span>
      </div>
      <div className="fact-grid">
        {eligible.map((f) => (
          <button
            className="fact-card"
            key={f.id}
            onClick={() =>
              onEvidence({
                id: f.chunk_id,
                document_id: f.document_id,
                title: f.title,
                company: f.company,
                page_index: f.page_index,
                text: f.source_text,
                synthetic: f.synthetic,
              })
            }
          >
            <div>
              {f.company}
              <span>{period(f.period_end)}</span>
            </div>
            <strong>
              {number(f.value)}
              <small>{f.units}</small>
            </strong>
            <span>
              {f.currency} · {f.basis} ·{" "}
              {f.synthetic ? "synthetic" : "reviewed"}{" "}
              <ArrowUpRight size={14} />
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
export function FactReviewList({
  facts,
  onRefresh,
  onEvidence,
  onError,
}: {
  facts: Fact[];
  onRefresh: () => Promise<void>;
  onEvidence: (e: Evidence) => void;
  onError: (s: string) => void;
}) {
  const [note, setNote] = useState(""),
    [active, setActive] = useState("");
  if (!facts.length) return null;
  return (
    <section className="fact-review">
      <h3>Values awaiting source review</h3>
      <p>
        These are extraction candidates. Inspect the source, then record your
        review.
      </p>
      {facts.map((f) => (
        <div key={f.id} className="review-row">
          <span>
            {f.company} · {f.metric.replaceAll("_", " ")} · {f.value} {f.units}
          </span>
          <button
            className="text-button"
            onClick={() => {
              setActive(f.id);
              onEvidence({
                id: f.chunk_id,
                document_id: f.document_id,
                title: f.title,
                company: f.company,
                page_index: f.page_index,
                text: f.source_text,
                synthetic: f.synthetic,
              });
            }}
          >
            Inspect source
          </button>
        </div>
      ))}
      {active && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api(`/facts/${active}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ verified: true, note }),
              });
              setActive("");
              setNote("");
              await onRefresh();
            } catch (err) {
              onError((err as Error).message);
            }
          }}
        >
          <label>
            Review note
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              required
              minLength={12}
              placeholder="Checked metric, period, basis and units against PDF…"
            />
          </label>
          <button className="button primary" disabled={note.length < 12}>
            Mark source checked
          </button>
        </form>
      )}
    </section>
  );
}
export function EvidencePanel({
  evidence: e,
  onClose,
}: {
  evidence: Evidence;
  onClose: () => void;
}) {
  const [page, setPage] = useState<{
      text: string;
      printed_label: string | null;
      tables: { id: string; cells: string[][] }[];
    } | null>(null),
    [error, setError] = useState(""),
    [pdf, setPdf] = useState(false);
  useEffect(() => {
    setPage(null);
    setError("");
    api<typeof page>(`/documents/${e.document_id}/pages/${e.page_index}`)
      .then(setPage)
      .catch((err) => setError(err.message));
  }, [e.document_id, e.page_index]);
  useEffect(() => {
    function close(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [onClose]);
  return (
    <div className="panel-overlay" onClick={onClose}>
      <aside
        className="evidence-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Evidence reader"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="panel-heading">
          <span>
            <BookOpen size={18} /> Evidence reader
          </span>
          <button aria-label="Close evidence reader" onClick={onClose}>
            <PanelRightClose size={21} />
          </button>
        </div>
        <div className="panel-doc">
          <span className="eyebrow">
            {e.synthetic ? "SYNTHETIC DEMO SOURCE" : "UPLOADED DISCLOSURE"}
          </span>
          <h2>{e.title}</h2>
          <div className="page-badge">
            PDF page {e.page_index + 1}
            <span>
              Printed label:{" "}
              {page?.printed_label || e.printed_label || "not available"}
            </span>
          </div>
        </div>
        <div className="reader-tabs">
          <button
            className={!pdf ? "selected" : ""}
            onClick={() => setPdf(false)}
          >
            Extracted text
          </button>
          <button
            className={pdf ? "selected" : ""}
            onClick={() => setPdf(true)}
          >
            PDF preview
          </button>
          <a
            href={`/api/documents/${e.document_id}/file#page=${e.page_index + 1}`}
            target="_blank"
            rel="noreferrer"
          >
            Open PDF <ExternalLink size={13} />
          </a>
        </div>
        {error ? (
          <div className="error">{error}</div>
        ) : pdf ? (
          <iframe
            title={`PDF page ${e.page_index + 1}`}
            src={`/api/documents/${e.document_id}/file#page=${e.page_index + 1}`}
          />
        ) : (
          <div className="reader-content">
            {!page ? (
              <LoaderCircle className="spin" />
            ) : (
              <>
                <div className="reader-text">{page.text}</div>
                {page.tables.length > 0 && (
                  <>
                    <h3>Extracted tables</h3>
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
        <div className="reader-footer">
          <ShieldCheck size={15} /> PDF page numbers are 1-based here. Printed
          labels may differ.
        </div>
      </aside>
    </div>
  );
}
export function UploadModal({
  onClose,
  onDone,
  maxUploadMb,
}: {
  onClose: () => void;
  onDone: () => Promise<void>;
  maxUploadMb: number;
}) {
  const [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [meta, setMeta] = useState({
      company: "",
      title: "",
      document_type: "quarterly_results",
      period_start: "",
      period_end: "",
      publication_date: "",
      source_url: "",
      currency: "INR",
      units: "crore",
      basis: "consolidated",
    });
  const update = (key: string, value: string) =>
    setMeta((m) => ({ ...m, [key]: value }));
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError("");
    setBusy(true);
    try {
      if (file.size > maxUploadMb * 1024 * 1024)
        throw new Error(
          `This PDF is ${(file.size / (1024 * 1024)).toFixed(1)} MB. The upload limit is ${maxUploadMb} MB.`,
        );
      const form = new FormData();
      form.append("file", file);
      form.append(
        "metadata",
        JSON.stringify({
          ...meta,
          publication_date: meta.publication_date || null,
          source_url: meta.source_url || null,
          units: meta.units || null,
        }),
      );
      const result = await api<{ duplicate: boolean }>("/documents", {
        method: "POST",
        body: form,
      });
      if (result.duplicate) {
        setError(
          "This exact PDF is already in the library. Existing metadata was retained.",
        );
        return;
      }
      await onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-overlay">
      <section
        className="upload-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Add a document"
      >
        <div className="modal-heading">
          <div>
            <span className="eyebrow">GROW YOUR CORPUS</span>
            <h2>Add a disclosure</h2>
          </div>
          <button aria-label="Close upload" onClick={onClose}>
            <X size={21} />
          </button>
        </div>
        <p>
          Upload a digitally generated PDF. Metadata keeps evidence in the right
          context.
        </p>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <form onSubmit={(e) => void submit(e)}>
          <label className="file-drop">
            <Upload size={26} />
            <strong>{file ? file.name : "Choose a PDF to upload"}</strong>
            <span>
              PDF only · Up to {maxUploadMb} MB · No scanned documents
            </span>
            {file && (
              <span>{(file.size / (1024 * 1024)).toFixed(1)} MB selected</span>
            )}
            <input
              type="file"
              aria-label="PDF file"
              accept="application/pdf,.pdf"
              required
              onChange={(e) => {
                const selected = e.target.files?.[0] || null;
                setFile(selected);
                setError(
                  selected && selected.size > maxUploadMb * 1024 * 1024
                    ? `This PDF is ${(selected.size / (1024 * 1024)).toFixed(1)} MB. The upload limit is ${maxUploadMb} MB.`
                    : "",
                );
              }}
            />
          </label>
          <div className="form-grid">
            <label>
              Company
              <input
                aria-label="Company name"
                required
                maxLength={100}
                value={meta.company}
                onChange={(e) => update("company", e.target.value)}
                placeholder="e.g. TCS"
              />
            </label>
            <label>
              Document type
              <select
                value={meta.document_type}
                onChange={(e) => update("document_type", e.target.value)}
              >
                <option value="quarterly_results">Quarterly results</option>
                <option value="annual_report">Annual report</option>
                <option value="presentation">Investor presentation</option>
                <option value="transcript">Earnings call transcript</option>
              </select>
            </label>
            <label className="wide">
              Document title
              <input
                required
                maxLength={240}
                value={meta.title}
                onChange={(e) => update("title", e.target.value)}
                placeholder="Company · Period · Disclosure"
              />
            </label>
            <label>
              Period start
              <input
                type="date"
                required
                value={meta.period_start}
                onChange={(e) => update("period_start", e.target.value)}
              />
            </label>
            <label>
              Period end
              <input
                type="date"
                required
                min={meta.period_start}
                value={meta.period_end}
                onChange={(e) => update("period_end", e.target.value)}
              />
            </label>
            <label>
              Publication date (if known)
              <input
                type="date"
                value={meta.publication_date}
                onChange={(e) => update("publication_date", e.target.value)}
              />
            </label>
            <label>
              Reporting basis
              <select
                value={meta.basis}
                onChange={(e) => update("basis", e.target.value)}
              >
                <option value="consolidated">Consolidated</option>
                <option value="standalone">Standalone</option>
              </select>
            </label>
            <label>
              Currency
              <select
                value={meta.currency}
                onChange={(e) => update("currency", e.target.value)}
              >
                {["INR", "USD", "EUR", "GBP"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              Units
              <select
                value={meta.units}
                onChange={(e) => update("units", e.target.value)}
              >
                <option value="">Unknown</option>
                {["unit", "lakh", "crore", "million", "billion"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="wide">
              Official source URL (optional)
              <input
                type="url"
                value={meta.source_url}
                onChange={(e) => update("source_url", e.target.value)}
                placeholder="https://…"
              />
            </label>
          </div>
          <div className="modal-actions">
            <button
              type="button"
              className="button secondary"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={busy || !file || file.size > maxUploadMb * 1024 * 1024}
            >
              {busy ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Upload size={16} />
              )}{" "}
              {busy ? "Uploading…" : "Upload & process"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
export function MethodView() {
  const [evaluation, setEvaluation] = useState<{
    k: number;
    limitations: string;
    summaries: {
      mode: string;
      recall_at_k: number;
      numerical_correct: number;
      unsupported_abstention_rate: number;
      latency_median_ms: number;
    }[];
  } | null>(null);
  useEffect(() => {
    fetch("/evaluation-summary.json")
      .then((r) => r.json())
      .then(setEvaluation)
      .catch(() => {});
  }, []);
  return (
    <div className="method-view">
      <div className="section-title">
        <h2>A small, inspectable research system</h2>
        <span>Portfolio edition</span>
      </div>
      <div className="method-grid">
        {[
          {
            icon: Search,
            title: "Three retrieval modes",
            body: "Keyword uses PostgreSQL full-text search. Vector uses cosine distance. Hybrid combines ranks with reciprocal rank fusion, constant 60. The offline vector baseline uses deterministic hashed words; it is not a semantic language model.",
          },
          {
            icon: ShieldCheck,
            title: "Evidence you can inspect",
            body: "Company, document type, reporting dates and publication cutoff narrow the corpus before retrieval. Every result links to a document and PDF page. Generated claims require retrieved IDs and matching quotations.",
          },
          {
            icon: ChartNoAxesCombined,
            title: "Arithmetic with guardrails",
            body: "Python Decimal handles units and changes. Percentage changes, percentage points and basis points are distinct. Inputs require source review. Unknown units and incompatible figures are rejected.",
          },
          {
            icon: FlaskConical,
            title: "Measured, with limits",
            body: "Fixed development and held-out questions compare retrieval on the same synthetic corpus. Reports include recall, citation checks, numeric accuracy, abstention and latency. Automated quote matching is not human semantic review.",
          },
        ].map((m) => (
          <article key={m.title}>
            <m.icon size={22} />
            <h3>{m.title}</h3>
            <p>{m.body}</p>
          </article>
        ))}
      </div>
      {evaluation && (
        <section className="evaluation-results">
          <div className="section-title">
            <h3>Recorded synthetic evaluation</h3>
            <span>10 initial held-out questions · k={evaluation.k}</span>
          </div>
          <div className="table-wrap">
            <table className="document-table">
              <thead>
                <tr>
                  <th>MODE</th>
                  <th>PAGE RECALL</th>
                  <th>NUMERICAL</th>
                  <th>UNSUPPORTED ABSTENTION</th>
                  <th>MEDIAN</th>
                </tr>
              </thead>
              <tbody>
                {evaluation.summaries.map((s) => (
                  <tr key={s.mode}>
                    <td>{s.mode}</td>
                    <td>{(s.recall_at_k * 100).toFixed(1)}%</td>
                    <td>{(s.numerical_correct * 100).toFixed(1)}%</td>
                    <td>{s.unsupported_abstention_rate * 100}%</td>
                    <td>{s.latency_median_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="footnote">{evaluation.limitations}</p>
        </section>
      )}
      <div className="principle-note">
        <AlertCircle size={23} />
        <div>
          <strong>Know what this demo can establish.</strong>
          <p>
            The included PDFs are invented fixtures. Extractive mode copies
            evidence and can miss paraphrases. Generative mode requires provider
            credentials. This local demo has no login or multi-user permissions
            and needs hardening before public deployment.
          </p>
        </div>
      </div>
      <a
        className="button secondary"
        href="/api/docs"
        target="_blank"
        rel="noreferrer"
      >
        Explore the API <ArrowUpRight size={16} />
      </a>
    </div>
  );
}
