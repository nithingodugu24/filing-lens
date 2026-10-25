import { useEffect, useState } from "react";
import { ArrowRight, Download, FileText, Search } from "lucide-react";
import {
  api,
  post,
  number,
  reportPeriod,
  type Answer,
  type Document,
  type Evidence,
  type MetricAnswer,
} from "./api";
import { MetricCard } from "./metric-card";
import { downloadReport } from "./export";

interface Workspace {
  financials: MetricAnswer[];
  evidence: Evidence[];
  brief: { status: string; content: Partial<Answer>; error: string | null };
  checks_explained: string;
}
interface LibraryItem {
  id: string;
  company: string;
  year: number;
  pages: number;
  url: string;
  prepared: boolean;
  document_id: string | null;
}

export function ReportHome({
  docs,
  activeId,
  onChoose,
  onAsk,
  onEvidence,
  onUpload,
  onCompare,
  onRefresh,
}: {
  docs: Document[];
  activeId: string;
  onChoose: (id: string) => void;
  onAsk: (q: string) => void;
  onEvidence: (e: Evidence) => void;
  onUpload: () => void;
  onCompare: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [data, setData] = useState<Workspace | null>(null),
    [library, setLibrary] = useState<LibraryItem[]>([]),
    [basis, setBasis] = useState("consolidated"),
    [error, setError] = useState(""),
    [opening, setOpening] = useState(""),
    [refreshKey, setRefreshKey] = useState(0);
  const doc =
    docs.find((d) => d.id === activeId) ||
    docs.find((d) => d.status === "indexed") ||
    docs[0];
  useEffect(() => {
    void api<LibraryItem[]>("/library")
      .then(setLibrary)
      .catch((e) => setError(e.message));
  }, [docs.length]);
  useEffect(() => {
    if (doc && doc.id !== activeId) onChoose(doc.id);
  }, [doc?.id, activeId]);
  useEffect(() => {
    setBasis(doc?.basis || "consolidated");
  }, [doc?.id]);
  useEffect(() => {
    setData(null);
    setError("");
    if (!doc || doc.status !== "indexed") return;
    let cancelled = false,
      timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const result = await api<Workspace>(
          `/documents/${doc.id}/workspace?basis=${basis}`,
        );
        if (cancelled) return;
        setData(result);
        if (result.brief.status === "preparing") timer = setTimeout(load, 5000);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    void load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [doc?.id, doc?.status, basis, refreshKey]);
  const sources = new Map(
    [...(data?.evidence || []), ...(data?.brief.content.evidence || [])].map(
      (e) => [e.id, e],
    ),
  );
  const latest =
    data?.financials.filter((m) => m.period_end === doc?.period_end) || [];
  const mainMetrics = ["revenue", "total_income", "net_profit"];
  const cards = latest.filter((m) => mainMetrics.includes(m.metric));
  async function openExample(item: LibraryItem) {
    setOpening(item.id);
    setError("");
    try {
      const result = await post<{ document_id: string }>(
        `/library/${item.id}/open`,
        {},
      );
      await onRefresh();
      onChoose(result.document_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOpening("");
    }
  }
  return (
    <div className="report-home">
      <div className="workspace-heading">
        <div>
          <span className="eyebrow">YOUR REPORT WORKSPACE</span>
          <h1>Read less. Understand more.</h1>
          <p>
            Key figures, a cited brief, and answers you can check against the
            report.
          </p>
        </div>
        <button className="button secondary" onClick={onUpload}>
          Upload a PDF <ArrowRight size={16} />
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {doc ? (
        <>
          <div className="workspace-toolbar">
            <label>
              Open a report
              <select
                aria-label="Open a report"
                value={doc.id}
                onChange={(e) => onChoose(e.target.value)}
              >
                {docs.map((d) => (
                  <option value={d.id} key={d.id}>
                    {d.title}
                    {d.status !== "indexed" ? " · Preparing" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Accounting basis
              <select
                aria-label="Accounting basis"
                value={basis}
                onChange={(e) => setBasis(e.target.value)}
              >
                <option value="consolidated">Consolidated</option>
                <option value="standalone">Standalone</option>
              </select>
            </label>
          </div>
          <section className="report-identity">
            <div>
              <h2>{doc.company}</h2>
              <p>
                {reportPeriod(doc.period_start, doc.period_end)} ·{" "}
                {doc.page_count} pages ·{" "}
                {doc.document_type.replaceAll("_", " ")}
              </p>
              <small>
                {doc.source_url ? (
                  <a href={doc.source_url} target="_blank" rel="noreferrer">
                    Report source ↗
                  </a>
                ) : (
                  "Uploaded report · source supplied by you"
                )}
              </small>
            </div>
            <div className="workspace-actions">
              <button
                className="button secondary"
                disabled={doc.status !== "indexed"}
                onClick={() =>
                  onEvidence({
                    id: doc.id,
                    document_id: doc.id,
                    title: doc.title,
                    company: doc.company,
                    page_index: 0,
                    text: "",
                    synthetic: doc.synthetic,
                  })
                }
              >
                <FileText size={16} /> Read PDF
              </button>
              <button
                className="button secondary"
                disabled={doc.status !== "indexed"}
                onClick={() =>
                  downloadReport([doc.id], "pdf", true).catch((e) =>
                    setError(e.message),
                  )
                }
              >
                <Download size={16} /> Export brief
              </button>
            </div>
          </section>
          {doc.status !== "indexed" ? (
            <section className="workspace-section">
              <h2>
                {doc.status === "failed"
                  ? "Your report needs attention"
                  : "Preparing your report"}
              </h2>
              {doc.status === "failed" && (
                <button
                  className="button secondary"
                  onClick={() =>
                    void post(`/documents/${doc.id}/retry`, {})
                      .then(onRefresh)
                      .catch((e) => setError(e.message))
                  }
                >
                  Retry report
                </button>
              )}
              <p>
                {doc.warning ||
                  "The report is waiting to be read. This page updates automatically."}
              </p>
            </section>
          ) : !data ? (
            <p className="skeleton" role="status">
              Loading source figures and brief…
            </p>
          ) : (
            <>
              <div className="metric-grid">
                {cards.map((m) => (
                  <MetricCard
                    key={m.fact_id}
                    metric={m}
                    evidence={sources.get(m.citation_id)}
                    onEvidence={onEvidence}
                  />
                ))}
              </div>
              {!cards.length && (
                <section className="workspace-section">
                  <h2>Figures need a closer look</h2>
                  <p>
                    We couldn't check the main financial rows in this layout.
                    Open the PDF or ask a sourced question; no estimated figures
                    are shown.
                  </p>
                </section>
              )}
              <div className="workspace-columns">
                <section className="workspace-section">
                  <div className="section-title">
                    <h2>What the report says</h2>
                    <span className="status indexed">
                      {data.brief.status === "ready"
                        ? "Cited brief"
                        : "Report brief"}
                    </span>
                  </div>
                  {data.brief.content.claims
                    ?.filter((c) => !data.brief.content.abstained)
                    .map((c, i) => (
                      <article className="brief-finding" key={i}>
                        <small className="eyebrow">{c.kind}</small>
                        <p>{c.text}</p>
                        <div className="citation-row">
                          {c.citation_ids.map((id) => {
                            const e = sources.get(id);
                            return (
                              e && (
                                <button
                                  className="citation"
                                  key={id}
                                  onClick={() =>
                                    onEvidence({
                                      ...e,
                                      highlightText: c.supporting_quote,
                                    })
                                  }
                                >
                                  <FileText size={14} /> PDF page{" "}
                                  {e.page_index + 1}
                                </button>
                              )
                            );
                          })}
                        </div>
                      </article>
                    ))}
                  {data.brief.status !== "ready" && (
                    <p>
                      {data.brief.status === "preparing"
                        ? "Preparing a short brief from the report. The financial figures are ready to use."
                        : data.brief.error ||
                          "A full narrative brief isn't available. Ask a specific question to explore the report with source references."}
                    </p>
                  )}
                  {!["ready", "preparing"].includes(data.brief.status) && (
                    <button
                      className="text-button"
                      onClick={() =>
                        void post(`/documents/${doc.id}/brief`, {})
                          .then(() => setRefreshKey((k) => k + 1))
                          .catch((e) => setError(e.message))
                      }
                    >
                      Prepare brief again
                    </button>
                  )}
                  <div className="brief-actions">
                    <button
                      className="button primary"
                      onClick={() =>
                        onAsk(
                          "What changed in the business this year, and what reasons did management give?",
                        )
                      }
                    >
                      Ask about this report <ArrowRight size={16} />
                    </button>
                  </div>
                </section>
                <section className="workspace-section">
                  <h2>Start with a useful question</h2>
                  <p>
                    Answers use this report and the accounting basis shown with
                    each figure.
                  </p>
                  {[
                    "What is the total income in crores this year?",
                    "How much did revenue grow this year?",
                    "What are the main business risks?",
                  ].map((q) => (
                    <button
                      className="workspace-question"
                      key={q}
                      onClick={() => onAsk(q)}
                    >
                      {q}
                      <ArrowRight size={16} />
                    </button>
                  ))}
                  <button className="text-button" onClick={onCompare}>
                    Compare checked figures <ArrowRight size={16} />
                  </button>
                </section>
              </div>
              {!!data.financials.length && (
                <section className="workspace-section">
                  <h2>Financial figures</h2>
                  <p>
                    {basis} · INR crore · year-on-year changes use matching
                    source rows
                  </p>
                  <div className="table-scroll">
                    <table className="financial-table">
                      <thead>
                        <tr>
                          <th>Figure</th>
                          <th>Latest year</th>
                          <th>Previous year</th>
                          <th>Change</th>
                          <th>Source</th>
                        </tr>
                      </thead>
                      <tbody>
                        {latest.map((m) => (
                          <tr key={m.fact_id}>
                            <td>{m.label}</td>
                            <td>
                              {number(m.value)} {m.units}
                            </td>
                            <td>
                              {m.previous_value !== null
                                ? `${number(m.previous_value)} ${m.units}`
                                : "Not checked"}
                            </td>
                            <td>
                              {m.change_percent !== null
                                ? `${number(m.change_percent)}%`
                                : "—"}
                            </td>
                            <td>
                              <button
                                className="citation"
                                onClick={() => {
                                  const e = sources.get(m.citation_id);
                                  if (e) onEvidence(e);
                                }}
                              >
                                Page {m.source_page}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <small>{data.checks_explained}</small>
                </section>
              )}
              <PeopleDirectory doc={doc} onEvidence={onEvidence} />
            </>
          )}
        </>
      ) : (
        <section className="workspace-section">
          <h2>Start with a real annual report</h2>
          <p>
            Open a prepared report below or upload a company PDF. Every figure
            links back to its source page.
          </p>
        </section>
      )}
      <section className="real-library">
        <div className="section-title">
          <h2>Explore real company reports</h2>
          <span>Original issuer PDFs</span>
        </div>
        <p>
          Prepared annual reports with financial figures and source references.
        </p>
        <div className="library-grid">
          {library.map((item) => (
            <article className="library-card" key={item.id}>
              <span className="eyebrow">ANNUAL REPORT</span>
              <h3>{item.company}</h3>
              <p>
                FY {item.year - 1}–{String(item.year).slice(-2)} · {item.pages}{" "}
                pages
              </p>
              <a href={item.url} target="_blank" rel="noreferrer">
                View issuer source ↗
              </a>
              <button
                className="button secondary"
                disabled={!item.prepared || !!opening}
                onClick={() => void openExample(item)}
              >
                {opening === item.id
                  ? "Opening…"
                  : item.prepared
                    ? "Open report"
                    : "Being prepared"}
                <ArrowRight size={15} />
              </button>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function PeopleDirectory({
  doc,
  onEvidence,
}: {
  doc: Document;
  onEvidence: (e: Evidence) => void;
}) {
  const [items, setItems] = useState<
      {
        id: string;
        text: string;
        type: string;
        count: number;
        mentions: { page_index: number; sentence: string }[];
      }[]
    >([]),
    [query, setQuery] = useState(""),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    setItems([]);
    setError("");
    if (open)
      void api<typeof items>(`/documents/${doc.id}/entities?mention_limit=1`)
        .then(setItems)
        .catch((e) => setError(e.message));
  }, [doc.id, open]);
  const useful = items
    .filter(
      (i) =>
        ["PERSON", "COMPANY"].includes(i.type) &&
        i.text.length > 4 &&
        i.text.length < 90 &&
        !/^(company|group|board|annual|refer|email|tcs|infosys|wipro|csr|llc|nil|limited|all|the )$/i.test(
          i.text,
        ) &&
        i.text.toLowerCase().includes(query.toLowerCase()),
    )
    .slice(0, 24);
  return (
    <details
      className="workspace-section"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>People and organisations mentioned</summary>
      {open && (
        <>
          <p>
            Names found in the report. Mentions do not prove a role, ownership
            or business relationship.
          </p>
          <label className="directory-search">
            <Search size={16} />
            <input
              aria-label="Search names"
              placeholder="Search a name"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          {error && <p role="alert">{error}</p>}
          <div className="people-grid">
            {useful.map((i) => (
              <button
                key={i.id}
                onClick={() => {
                  const mention = i.mentions[0];
                  if (mention)
                    onEvidence({
                      id: i.id,
                      document_id: doc.id,
                      title: doc.title,
                      company: doc.company,
                      page_index: mention.page_index,
                      text: mention.sentence,
                      synthetic: doc.synthetic,
                      highlightText: i.text,
                    });
                }}
              >
                <strong>{i.text}</strong>
                <small>
                  {i.type === "PERSON" ? "Person" : "Organisation"} · open
                  mention
                </small>
              </button>
            ))}
          </div>
          {!useful.length && (
            <p>
              No matching names have been prepared. You can still search the
              report through questions.
            </p>
          )}
          <small>Showing up to 24 matching names.</small>
        </>
      )}
    </details>
  );
}
