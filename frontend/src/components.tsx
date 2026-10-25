export { UploadModal } from "./upload";
import React, { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  ChartNoAxesCombined,
  Check,
  Clock3,
  FileText,
  FlaskConical,
  LoaderCircle,
  Search,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";
import {
  api,
  post,
  number,
  reportPeriod,
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
            <th>Report</th>
            <th>Company</th>
            <th>Period</th>
            <th>Status</th>
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
                      {d.synthetic ? "Made-up sample" : d.basis} ·{" "}
                      {d.page_count} pages
                    </small>
                  </span>
                </button>
                {d.warning && (
                  <div
                    className={
                      d.status === "processing"
                        ? "document-progress"
                        : "document-warning"
                    }
                  >
                    {d.warning}
                  </div>
                )}
              </td>
              <td>
                <span className="table-company">{d.company}</span>
              </td>
              <td>{reportPeriod(d.period_start, d.period_end)}</td>
              <td>
                <span className={`status ${d.status}`}>
                  {d.status === "indexed" ? (
                    <Check size={12} />
                  ) : d.status === "failed" ? (
                    <AlertCircle size={12} />
                  ) : (
                    <Clock3 size={12} />
                  )}{" "}
                  {d.status === "indexed"
                    ? "Ready"
                    : d.status === "failed"
                      ? "Needs attention"
                      : d.status === "queued"
                        ? "Waiting"
                        : "Preparing"}
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
                    Open report <ArrowUpRight size={17} />
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!docs.length && (
        <div className="table-empty">
          No reports match your selection. Choose another company or period.
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
        <span>Calculated from checked figures</span>
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
              {i === 0 ? "FIRST REPORT" : "SECOND REPORT"} ·{" "}
              {reportPeriod(
                v.period.calendar.split(" to ")[0],
                v.period.calendar.split(" to ")[1],
              )}
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
        <summary>Show unit conversions</summary>
        <pre>{JSON.stringify(c.normalised_inputs, null, 2)}</pre>
      </details>
      <div className="citation-row">
        {sources.map((e, i) => (
          <button key={i} className="citation" onClick={() => onEvidence(e)}>
            <FileText size={13} />
            Open {e.company} source · page {e.page_index + 1}
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
        <h2>Choose what to compare</h2>
        <span>
          <ShieldCheck size={15} /> {eligible.length} checked figures available
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
                  e.target.value !== "operating_margin"
                    ? "percentage_change"
                    : "percentage_points",
                );
              }}
            >
              <option value="revenue">Revenue</option>
              <option value="total_income">Total income</option>
              <option value="net_profit">Profit for the year</option>
              <option value="other_income">Other income</option>
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
              {metric !== "operating_margin" ? (
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
            { label: "First report", value: first, set: setFirst },
            { label: "Second report", value: second, set: setSecond },
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
                      {f.company} · {reportPeriod(f.period_start, f.period_end)}{" "}
                      · {number(f.value)} {f.units} ·{" "}
                      {f.synthetic ? "synthetic" : f.basis}
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
          Compare numbers
        </button>
      </div>
      {result && (
        <CalculationCard calculation={result} onEvidence={onEvidence} />
      )}
      <div className="principle-note">
        <ShieldCheck size={21} />
        <div>
          <strong>We check the figures before comparing them.</strong>
          <p>
            Both figures must use compatible dates, currency and reporting
            rules. If no checked figures are available, look in My reports for
            values to review. You can still ask questions about the report text.
          </p>
        </div>
      </div>
      <div className="section-title">
        <h3>Available figures — click to check the source</h3>
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
              <span>{reportPeriod(f.period_start, f.period_end)}</span>
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
      <h3>Check these numbers before comparing</h3>
      <p>
        These numbers were recognised automatically and may be wrong. Open the
        report, check the value, period and units, then add a note to confirm.
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
            Check source
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
export { EvidencePanel } from "./evidence-panel";
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
