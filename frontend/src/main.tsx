import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  ChartNoAxesCombined,
  Check,
  FileText,
  HelpCircle,
  LoaderCircle,
  MessageSquare,
  Upload,
  X,
  Download,
  Moon,
  Sun,
  Network,
} from "lucide-react";
import {
  api,
  post,
  reportPeriod,
  type Answer,
  type Document,
  type Evidence,
  type Fact,
  type RuntimeInfo,
} from "./api";
import {
  CalculationCard,
  CompareView,
  DocumentTable,
  FactReviewList,
  MethodView,
  UploadModal,
} from "./components";
import "./style.css";
import { Conversation, Confidence } from "./conversation";
import { AuthProvider, useAuth } from "./auth";
import { ExportModal, downloadReport } from "./export";
import { connectStatus } from "./websocket";

const Dashboard = React.lazy(() =>
  import("./dashboard").then((module) => ({ default: module.Dashboard })),
);
const KnowledgeGraph = React.lazy(() =>
  import("./knowledge-graph").then((module) => ({
    default: module.KnowledgeGraph,
  })),
);
const EvidencePanel = React.lazy(() =>
  import("./evidence-panel").then((module) => ({
    default: module.EvidencePanel,
  })),
);

type View = "ask" | "reports" | "compare" | "dashboard" | "graph" | "help";
type ReportSet = "uploaded" | "samples";
const questions = [
  "Compare revenue growth for TCS and Infosys.",
  "What changed in operating margin between these quarters?",
  "What explanation did management give for the margin change?",
];

function App() {
  const { user, logout } = useAuth();
  const [exportOpen, setExportOpen] = useState(false),
    [connected, setConnected] = useState(false);
  const [theme, setTheme] = useState(
    () =>
      localStorage.getItem("filinglens-theme") ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("filinglens-theme", theme);
  }, [theme]);
  const [view, setView] = useState<View>("ask"),
    [docs, setDocs] = useState<Document[]>([]),
    [facts, setFacts] = useState<Fact[]>([]),
    [ready, setReady] = useState<Partial<RuntimeInfo>>({});
  const [source, setSource] = useState<ReportSet>("uploaded"),
    [company, setCompany] = useState("all"),
    [selectedPeriod, setPeriod] = useState("all"),
    [docType, setDocType] = useState("all"),
    [cutoff, setCutoff] = useState(""),
    [mode, setMode] = useState("keyword");
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [upload, setUpload] = useState(false),
    [selected, setSelected] = useState<Evidence | null>(null);
  const [question, setQuestion] = useState(""),
    [asked, setAsked] = useState(""),
    [answer, setAnswer] = useState<Answer | null>(null);
  const questionInput = useRef<HTMLTextAreaElement>(null);
  const [conversationMode, setConversationMode] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const [d, f, r] = await Promise.all([
        api<Document[]>("/documents"),
        api<Fact[]>("/facts"),
        api<RuntimeInfo>("/ready"),
      ]);
      setDocs(d);
      setFacts(f);
      setReady(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(
    () =>
      connectStatus((event) => {
        if (event.type === "connected") {
          void refresh();
          return;
        }
        if (event.document_id) {
          setDocs((current) =>
            current.map((d) =>
              d.id === event.document_id
                ? {
                    ...d,
                    status: event.status ?? d.status,
                    warning:
                      event.progress === undefined ? d.warning : event.progress,
                    page_count: event.page_count ?? d.page_count,
                  }
                : d,
            ),
          );
          if (event.type === "job_complete") {
            setNotice("Your report is ready. You can now ask questions.");
            void refresh();
          } else if (event.status === "failed") {
            setNotice("A report needs attention. Open My reports for details.");
            void refresh();
          }
        }
      }, setConnected),
    [refresh],
  );
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 60000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (questionInput.current) {
      questionInput.current.style.height = "auto";
      questionInput.current.style.height =
        Math.min(160, Math.max(100, questionInput.current.scrollHeight)) + "px";
    }
  }, [question]);
  useEffect(() => {
    setAnswer(null);
    setAsked("");
  }, [source, company, selectedPeriod, docType, cutoff]);
  const sourceDocs = docs.filter((d) => d.synthetic === (source === "samples"));
  const companies = [...new Set(sourceDocs.map((d) => d.company))].sort();
  const periods = [...new Set(sourceDocs.map((d) => d.period_end))]
    .sort()
    .reverse();
  const filtered = sourceDocs.filter(
    (d) =>
      (company === "all" || d.company === company) &&
      (selectedPeriod === "all" || d.period_end === selectedPeriod) &&
      (docType === "all" || d.document_type === docType) &&
      (!cutoff ||
        (d.publication_date !== null && d.publication_date <= cutoff)),
  );
  const filteredFacts = facts.filter((f) =>
    filtered.some((d) => d.id === f.document_id),
  );
  const searchable = filtered.filter((d) => d.status === "indexed");
  const sampleCount = docs.filter((d) => d.synthetic).length,
    uploadedCount = docs.length - sampleCount;
  function changeSource(value: ReportSet) {
    setSource(value);
    setCompany("all");
    setPeriod("all");
    setDocType("all");
    setCutoff("");
    setError("");
  }
  function navigate(next: View) {
    setView(next);
    setError("");
  }
  async function trySamples() {
    changeSource("samples");
    if (!sampleCount) {
      setBusy(true);
      try {
        await post("/demo", {});
        await refresh();
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    }
  }
  async function ask(text = question) {
    if (busy || text.trim().length < 3 || !searchable.length) return;
    setBusy(true);
    setError("");
    setAnswer(null);
    setAsked(text);
    setQuestion(text);
    try {
      setAnswer(
        await post<Answer>("/questions", {
          question: text,
          mode,
          k: 8,
          filters: {
            synthetic: source === "samples",
            companies: company === "all" ? [] : [company],
            period_ends: selectedPeriod === "all" ? [] : [selectedPeriod],
            document_types: docType === "all" ? [] : [docType],
            publication_cutoff: cutoff || null,
          },
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function openDoc(d: Document) {
    setSelected({
      id: d.id,
      document_id: d.id,
      title: d.title,
      company: d.company,
      page_index: 0,
      text: "",
      synthetic: d.synthetic,
    });
  }
  async function retry(id: string) {
    try {
      await post(`/documents/${id}/retry`, {});
      setNotice("Trying again. The report status will update automatically.");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const evidenceById = new Map(answer?.evidence.map((e) => [e.id, e]) || []);
  return (
    <div className="simple-app">
      <header className="app-header">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("ask");
          }}
        >
          <span className="brand-icon">
            <FileText size={22} />
          </span>
          FilingLens
        </a>
        <span className="brand-description">Understand company reports</span>
        <span
          className={`connection-dot ${connected ? "online" : "offline"}`}
          title={
            connected
              ? "Live updates connected"
              : "Reconnecting to live updates"
          }
          aria-label={
            connected ? "Live updates connected" : "Live updates disconnected"
          }
        />
        <button
          className="icon-button"
          aria-label={theme === "dark" ? "Use light theme" : "Use dark theme"}
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        >
          {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
        </button>
        <button
          className="button secondary header-export"
          onClick={() => setExportOpen(true)}
        >
          <Download size={17} />
          <span>Export</span>
        </button>
        {user && (
          <details className="user-menu">
            <summary>{user.full_name}</summary>
            <small>{user.role}</small>
            <button onClick={logout}>Sign out</button>
          </details>
        )}
        <button className="button primary" onClick={() => setUpload(true)}>
          <Upload size={18} />
          Upload report
        </button>
      </header>
      <div className="app-container">
        <nav className="main-nav" aria-label="Main navigation">
          {(
            [
              { id: "ask", label: "Ask a question", icon: MessageSquare },
              { id: "reports", label: "My reports", icon: FileText },
              {
                id: "compare",
                label: "Compare numbers",
                icon: ChartNoAxesCombined,
              },
              {
                id: "dashboard",
                label: "Dashboard",
                icon: ChartNoAxesCombined,
              },
              { id: "graph", label: "Knowledge graph", icon: Network },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              aria-label={item.label}
              aria-current={view === item.id ? "page" : undefined}
              className={view === item.id ? "selected" : ""}
              onClick={() => navigate(item.id)}
            >
              <item.icon size={18} />
              <span className="nav-label">{item.label}</span>
              <span className="nav-short">
                {
                  {
                    ask: "Ask",
                    reports: "Reports",
                    compare: "Compare",
                    dashboard: "Charts",
                    graph: "Names",
                  }[item.id]
                }
              </span>
            </button>
          ))}
        </nav>
        <main>
          <div className="breadcrumb">
            <button onClick={() => navigate("ask")}>Home</button>
            <span>›</span>
            <span>
              {
                {
                  ask: "Ask a question",
                  reports: "My reports",
                  compare: "Compare numbers",
                  dashboard: "Dashboard",
                  graph: "Knowledge graph",
                  help: "Help",
                }[view]
              }
            </span>
            {upload && <span>› Upload report</span>}
          </div>
          <div className="page-heading">
            <h1>
              {view === "ask"
                ? "Ask questions about company reports"
                : view === "reports"
                  ? "Your reports"
                  : view === "compare"
                    ? "Compare financial numbers"
                    : view === "dashboard"
                      ? "Financial dashboard"
                      : view === "graph"
                        ? "Names and figures in your reports"
                        : "How FilingLens works"}
            </h1>
            <p>
              {view === "ask"
                ? "Choose your reports, ask a question, and check the source page."
                : view === "reports"
                  ? "Upload a PDF and wait until it says “Ready”. Then you can ask questions about it."
                  : view === "compare"
                    ? "Choose two checked figures to see the change and how it was calculated."
                    : view === "dashboard"
                      ? "See trends from checked figures in your reports."
                      : view === "graph"
                        ? "Explore names, dates and figures mentioned together, then check the source."
                        : "Answers come from the reports you select. You can open the source for every result."}
            </p>
          </div>
          {error && (
            <div className="error" role="alert">
              <AlertCircle size={20} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={18} />
              </button>
            </div>
          )}
          {notice && (
            <div className="success-message" role="status">
              <Check size={18} />
              <span>{notice}</span>
              <button
                aria-label="Dismiss message"
                onClick={() => setNotice("")}
              >
                <X size={18} />
              </button>
            </div>
          )}
          {loading ? (
            <div className="skeleton" role="status">
              Loading reports…
            </div>
          ) : (
            <>
              {view !== "help" && (
                <>
                  <div className="report-filters">
                    <label>
                      Reports to use
                      <select
                        aria-label="Reports to use"
                        value={source}
                        disabled={busy}
                        onChange={(e) =>
                          changeSource(e.target.value as ReportSet)
                        }
                      >
                        <option value="uploaded">
                          My uploaded reports ({uploadedCount})
                        </option>
                        <option value="samples">
                          Sample reports ({sampleCount})
                        </option>
                      </select>
                    </label>
                    <label>
                      Company
                      <select
                        aria-label="Company filter"
                        value={company}
                        disabled={busy || !sourceDocs.length}
                        onChange={(e) => setCompany(e.target.value)}
                      >
                        <option value="all">All companies</option>
                        {companies.map((c) => (
                          <option key={c}>{c}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Reporting period
                      <select
                        aria-label="Period filter"
                        value={selectedPeriod}
                        disabled={busy || !sourceDocs.length}
                        onChange={(e) => setPeriod(e.target.value)}
                      >
                        <option value="all">All periods</option>
                        {periods.map((p) => (
                          <option key={p} value={p}>
                            {reportPeriod(
                              sourceDocs.find((d) => d.period_end === p)!
                                .period_start,
                              p,
                            )}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  {source === "samples" && (
                    <div className="sample-notice">
                      <AlertCircle size={19} />
                      <span>
                        <strong>These are sample reports.</strong> All figures
                        are made up. Upload your own PDF to work with real
                        disclosures.
                      </span>
                    </div>
                  )}
                </>
              )}
              {!sourceDocs.length && view !== "help" ? (
                <section className="getting-started">
                  <div className="welcome-icon">
                    <Upload size={28} />
                  </div>
                  <h2>
                    {source === "uploaded"
                      ? "Start with a company report"
                      : "Try the sample reports"}
                  </h2>
                  <p>
                    {source === "uploaded"
                      ? "Upload an annual report, quarterly result, presentation, or earnings-call transcript."
                      : "Use four made-up TCS and Infosys reports to try questions and comparisons."}
                  </p>
                  <div className="welcome-actions">
                    {source === "uploaded" && (
                      <button
                        className="button primary"
                        onClick={() => setUpload(true)}
                      >
                        <Upload size={18} />
                        Upload your first report
                      </button>
                    )}
                    <button
                      className="button secondary"
                      disabled={busy}
                      onClick={() => void trySamples()}
                    >
                      {busy ? (
                        <LoaderCircle className="spin" size={18} />
                      ) : (
                        <BookOpen size={18} />
                      )}{" "}
                      {source === "uploaded"
                        ? "Try with sample reports"
                        : "Load sample reports"}
                    </button>
                  </div>
                  <ol className="quick-steps">
                    <li>
                      <span>1</span>Upload a PDF
                    </li>
                    <li>
                      <span>2</span>Ask your question
                    </li>
                    <li>
                      <span>3</span>Open the source page
                    </li>
                  </ol>
                </section>
              ) : (
                <>
                  {view === "ask" && ready.answer_provider && (
                    <div
                      className={`ai-service-status ${ready.answer_provider === "extractive" ? "offline" : ""}`}
                      role="status"
                    >
                      {ready.answer_provider === "extractive"
                        ? "AI answers are off. This mode shows passages from your reports."
                        : ready.answer_status === "needs_setup"
                          ? "AI answers need setup. Check the service key and selected model."
                          : `AI answers enabled · ${ready.answer_service || "Configured AI service"}${ready.answer_model ? " · " + ready.answer_model : ""}`}
                    </div>
                  )}
                  {view === "ask" &&
                    filtered.length > 0 &&
                    !searchable.length && (
                      <section className="report-state">
                        <AlertCircle size={22} />
                        <div>
                          <h2>
                            {filtered.some((d) => d.status === "failed")
                              ? "Your report needs attention"
                              : "Your reports are being prepared"}
                          </h2>
                          <p>
                            {filtered.some((d) => d.status === "failed")
                              ? "A report could not be processed. Open its status to see the reason and retry."
                              : "You can ask questions once the status changes to Ready. This page updates automatically."}
                          </p>
                          <button
                            className="text-button"
                            onClick={() => navigate("reports")}
                          >
                            View report status
                            <ArrowRight size={15} />
                          </button>
                        </div>
                      </section>
                    )}
                  {view === "ask" && searchable.length > 0 && (
                    <div
                      className="question-mode"
                      role="group"
                      aria-label="Question mode"
                    >
                      <button
                        className={!conversationMode ? "selected" : ""}
                        onClick={() => setConversationMode(false)}
                      >
                        Single question
                      </button>
                      <button
                        className={conversationMode ? "selected" : ""}
                        onClick={() => setConversationMode(true)}
                      >
                        Conversation mode
                      </button>
                    </div>
                  )}
                  {view === "ask" &&
                    conversationMode &&
                    searchable.length > 0 && (
                      <Conversation
                        key={[
                          source,
                          company,
                          selectedPeriod,
                          docType,
                          cutoff,
                        ].join("|")}
                        filters={{
                          synthetic: source === "samples",
                          companies: company === "all" ? [] : [company],
                          period_ends:
                            selectedPeriod === "all" ? [] : [selectedPeriod],
                          document_types: docType === "all" ? [] : [docType],
                          publication_cutoff: cutoff || null,
                        }}
                        mode={mode}
                        onEvidence={setSelected}
                      />
                    )}
                  {view === "ask" && !conversationMode && (
                    <div className="ask-layout">
                      <div className="question-and-answer">
                        <section className="question-card">
                          <div className="question-heading">
                            <h2>What would you like to know?</h2>
                            <span className="ready-count">
                              {searchable.length}{" "}
                              {source === "samples" ? "sample " : ""}report
                              {searchable.length === 1 ? "" : "s"} ready
                            </span>
                          </div>
                          <form
                            onSubmit={(e) => {
                              e.preventDefault();
                              void ask();
                            }}
                          >
                            <label className="sr-only" htmlFor="question">
                              Your question
                            </label>
                            <textarea
                              id="question"
                              ref={questionInput}
                              placeholder="For example: Why did operating margin change?"
                              value={question}
                              onChange={(e) => setQuestion(e.target.value)}
                              maxLength={2000}
                              onKeyDown={(e) => {
                                if (
                                  e.key === "Enter" &&
                                  (e.ctrlKey || e.metaKey)
                                ) {
                                  e.preventDefault();
                                  void ask();
                                }
                              }}
                            />
                            <div className="composer-bottom">
                              <span>
                                {!searchable.length
                                  ? "No ready reports match your selection."
                                  : ready.answer_provider === "extractive"
                                    ? "Works offline: explains report details and finds passages in the selected reports."
                                    : "Answers will use only the reports selected above."}
                              </span>
                              <button
                                className="button primary"
                                disabled={
                                  busy ||
                                  question.trim().length < 3 ||
                                  !searchable.length
                                }
                              >
                                {busy ? (
                                  <LoaderCircle className="spin" size={18} />
                                ) : (
                                  <ArrowRight size={18} />
                                )}{" "}
                                {busy ? "Finding an answer…" : "Find answer"}
                              </button>
                            </div>
                          </form>
                          <div className="example-questions">
                            <span>Try a question:</span>
                            {[
                              {
                                label: "What is this report?",
                                text: "What is this report?",
                              },
                              {
                                label: "Compare revenue growth",
                                text: questions[0],
                              },
                              {
                                label: "Why did margins change?",
                                text: questions[1],
                              },
                              {
                                label: "What did management say?",
                                text: questions[2],
                              },
                            ].map((q) => (
                              <button
                                key={q.label}
                                disabled={busy || !searchable.length}
                                onClick={() => void ask(q.text)}
                              >
                                {q.label}
                                <ArrowRight size={14} />
                              </button>
                            ))}
                          </div>
                          <details className="search-options">
                            <summary>More search options</summary>
                            <div className="advanced-filters">
                              <label>
                                Report type
                                <select
                                  aria-label="Document type filter"
                                  value={docType}
                                  disabled={busy}
                                  onChange={(e) => setDocType(e.target.value)}
                                >
                                  <option value="all">All types</option>
                                  <option value="quarterly_results">
                                    Quarterly results
                                  </option>
                                  <option value="annual_report">
                                    Annual reports
                                  </option>
                                  <option value="presentation">
                                    Presentations
                                  </option>
                                  <option value="transcript">
                                    Call transcripts
                                  </option>
                                </select>
                              </label>
                              <label>
                                Published on or before
                                <input
                                  aria-label="Publication cutoff"
                                  type="date"
                                  disabled={busy}
                                  value={cutoff}
                                  onChange={(e) => setCutoff(e.target.value)}
                                />
                              </label>
                              <label>
                                Search method
                                <select
                                  aria-label="Retrieval mode"
                                  disabled={busy}
                                  value={mode}
                                  onChange={(e) => setMode(e.target.value)}
                                >
                                  <option value="keyword">Match words</option>
                                  <option value="vector">
                                    Word-vector search (offline baseline)
                                  </option>
                                  <option value="hybrid">
                                    Combine both methods
                                  </option>
                                </select>
                              </label>
                              <p>
                                A date cutoff excludes reports with an unknown
                                publication date. Sample vectors match
                                vocabulary; they do not understand meaning.
                              </p>
                            </div>
                          </details>
                        </section>
                        {busy && (
                          <div className="searching" role="status">
                            <LoaderCircle className="spin" size={22} />
                            Reading the selected reports…
                          </div>
                        )}
                        {answer && (
                          <section
                            className="answer-section"
                            aria-live="polite"
                          >
                            <div className="section-title">
                              <h2>
                                {answer.answer_kind === "report_overview"
                                  ? answer.report_overviews?.length === 1
                                    ? "About this report"
                                    : "About these reports"
                                  : answer.answer_kind === "clarification"
                                    ? "What would you like to understand?"
                                    : answer.answer_kind === "help"
                                      ? "How FilingLens can help"
                                      : answer.abstained
                                        ? "I couldn't find a supported answer"
                                        : "Results from your reports"}
                              </h2>
                              <button
                                className="text-button"
                                onClick={() => {
                                  setAnswer(null);
                                  setQuestion("");
                                  questionInput.current?.focus();
                                }}
                              >
                                Clear answer
                              </button>
                            </div>
                            <p className="asked-question">{asked}</p>
                            <button
                              className="text-button answer-export"
                              onClick={() =>
                                downloadReport(
                                  [
                                    ...new Set(
                                      answer.evidence.map((e) => e.document_id),
                                    ),
                                  ],
                                  "md",
                                  true,
                                  answer.run_id,
                                ).catch((e) => setError(e.message))
                              }
                              disabled={!answer.evidence.length}
                            >
                              <Download size={14} /> Save answer
                            </button>
                            <Confidence value={answer.confidence} />
                            {answer.summary && (
                              <div className="reply-summary">
                                <p>{answer.summary}</p>
                              </div>
                            )}
                            {answer.report_overviews?.map((report) => {
                              const evidence = evidenceById.get(
                                report.citation_id,
                              );
                              return (
                                <article
                                  className="report-overview"
                                  key={report.document_id}
                                >
                                  <h3>{report.title}</h3>
                                  <p>
                                    {report.company} ·{" "}
                                    {reportPeriod(
                                      report.period_start,
                                      report.period_end,
                                    )}{" "}
                                    · {report.page_count} pages
                                    {report.synthetic
                                      ? " · Made-up sample"
                                      : ""}
                                  </p>
                                  {evidence && (
                                    <button
                                      className="citation"
                                      onClick={() => setSelected(evidence)}
                                    >
                                      <FileText size={16} />
                                      Open report · page{" "}
                                      {evidence.page_index + 1}
                                      <ArrowRight size={14} />
                                    </button>
                                  )}
                                </article>
                              );
                            })}
                            {answer.answer_kind &&
                            answer.answer_kind !== "answer" ? (
                              <p className="context-explanation">
                                {answer.limitation}
                              </p>
                            ) : answer.abstained ? (
                              <p className="abstention">{answer.limitation}</p>
                            ) : (
                              <>
                                {answer.calculations.map((c, i) => (
                                  <CalculationCard
                                    key={i}
                                    calculation={c}
                                    evidence={answer.evidence}
                                    onEvidence={setSelected}
                                  />
                                ))}
                                <div className="answer-explanation">
                                  {answer.mode === "extractive"
                                    ? "The passages below are copied from the reports. Open the source page to check the full context."
                                    : answer.limitation}
                                </div>
                                {answer.mode === "extractive" &&
                                  /conflict/i.test(answer.limitation) && (
                                    <p className="sample-notice">
                                      {answer.limitation}
                                    </p>
                                  )}
                                {answer.claims.map((claim, i) => (
                                  <article className="claim" key={i}>
                                    <h3>
                                      {claim.citation_ids
                                        .map(
                                          (id) => evidenceById.get(id)?.company,
                                        )
                                        .filter(
                                          (v, i, a) => v && a.indexOf(v) === i,
                                        )
                                        .join(" · ")}
                                      <span>
                                        {claim.kind === "source excerpt"
                                          ? "Report excerpt"
                                          : claim.kind}
                                      </span>
                                    </h3>
                                    {claim.text.length > 550 ? (
                                      <details className="long-excerpt">
                                        <summary>
                                          {claim.text.slice(0, 450)}…{" "}
                                          <strong>Read full passage</strong>
                                        </summary>
                                        <p>{claim.text}</p>
                                      </details>
                                    ) : (
                                      <p>{claim.text}</p>
                                    )}
                                    <div className="citation-row">
                                      {claim.citation_ids.map((id) => {
                                        const e = evidenceById.get(id);
                                        return e ? (
                                          <button
                                            className="citation"
                                            key={id}
                                            onClick={() =>
                                              setSelected({
                                                ...e,
                                                highlightText:
                                                  claim.supporting_quote,
                                              })
                                            }
                                          >
                                            <FileText size={16} />
                                            Open {e.company} source · page{" "}
                                            {e.page_index + 1}
                                            <ArrowRight size={14} />
                                          </button>
                                        ) : null;
                                      })}
                                    </div>
                                  </article>
                                ))}
                              </>
                            )}
                            {!!answer.suggestions?.length && (
                              <div className="answer-suggestions">
                                <strong>
                                  {answer.answer_kind === "report_overview"
                                    ? "What would you like to explore?"
                                    : "Try one of these questions"}
                                </strong>
                                {answer.suggestions.map((suggestion) => (
                                  <button
                                    className="suggestion-button"
                                    key={suggestion}
                                    disabled={busy}
                                    onClick={() => void ask(suggestion)}
                                  >
                                    {suggestion}
                                    <ArrowRight size={16} />
                                  </button>
                                ))}
                              </div>
                            )}
                            <details className="run-details">
                              <summary>Sources and technical details</summary>
                              <div className="source-list">
                                {answer.evidence.map((e) => (
                                  <button
                                    key={e.id}
                                    onClick={() => setSelected(e)}
                                  >
                                    <FileText size={16} />
                                    {e.title} · page {e.page_index + 1}
                                  </button>
                                ))}
                              </div>
                              <pre>
                                {JSON.stringify(
                                  {
                                    configuration: answer.configuration,
                                    usage: answer.usage,
                                    cost_usd: answer.cost_usd,
                                  },
                                  null,
                                  2,
                                )}
                              </pre>
                            </details>
                          </section>
                        )}
                      </div>
                      <aside className="selected-reports">
                        <div className="section-title">
                          <h2>Reports being used</h2>
                          <span>{filtered.length}</span>
                        </div>
                        <p>Only reports marked Ready can answer questions.</p>
                        {filtered.slice(0, 8).map((d) => (
                          <button
                            key={d.id}
                            onClick={() => openDoc(d)}
                            disabled={d.status !== "indexed"}
                          >
                            <FileText size={19} />
                            <span>
                              <strong>{d.company}</strong>
                              <span>
                                {reportPeriod(d.period_start, d.period_end)} ·{" "}
                                {d.document_type === "annual_report"
                                  ? "Annual report"
                                  : d.document_type.replaceAll("_", " ")}
                              </span>
                              <small
                                className={
                                  d.status === "indexed" ? "is-ready" : ""
                                }
                              >
                                {d.status === "indexed"
                                  ? "Ready"
                                  : d.status === "failed"
                                    ? "Needs attention"
                                    : "Preparing…"}
                              </small>
                            </span>
                          </button>
                        ))}
                        {!filtered.length && (
                          <p>No reports match. Change the filters above.</p>
                        )}
                        <button
                          className="text-button manage-reports"
                          onClick={() => navigate("reports")}
                        >
                          View all reports
                          <ArrowRight size={15} />
                        </button>
                      </aside>
                    </div>
                  )}
                  {view === "reports" && (
                    <section className="reports-section">
                      <div className="section-title">
                        <h2>
                          {source === "samples"
                            ? "Sample reports"
                            : "Uploaded reports"}
                        </h2>
                        <button
                          className="text-button"
                          onClick={() => void refresh()}
                        >
                          Refresh status
                        </button>
                      </div>
                      <DocumentTable
                        docs={filtered}
                        onOpen={openDoc}
                        onRetry={retry}
                      />
                      <p className="footnote">
                        PDFs up to {ready.max_upload_mb ?? 100} MB. Scanned
                        reports need text recognition before upload.
                      </p>
                      <FactReviewList
                        facts={filteredFacts.filter((f) => !f.verified)}
                        onRefresh={refresh}
                        onEvidence={setSelected}
                        onError={setError}
                      />
                    </section>
                  )}
                  {view === "compare" && (
                    <CompareView
                      facts={filteredFacts}
                      onEvidence={setSelected}
                      onError={setError}
                    />
                  )}
                  {view === "dashboard" && (
                    <React.Suspense
                      fallback={
                        <div className="skeleton">Loading dashboard…</div>
                      }
                    >
                      <Dashboard
                        synthetic={source === "samples"}
                        documentIds={filtered.map((d) => d.id)}
                      />
                    </React.Suspense>
                  )}
                  {view === "graph" && (
                    <React.Suspense
                      fallback={
                        <div className="skeleton">
                          Loading names and figures…
                        </div>
                      }
                    >
                      <KnowledgeGraph
                        key={source}
                        docs={filtered}
                        onEvidence={setSelected}
                      />
                    </React.Suspense>
                  )}
                </>
              )}
              {view === "help" && <MethodView />}
            </>
          )}
        </main>
        <footer>
          <span>FilingLens · Indian company reports</span>
          <button onClick={() => navigate("help")}>
            <HelpCircle size={16} />
            How answers work
          </button>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            API documentation
          </a>
        </footer>
      </div>
      {selected && (
        <React.Suspense
          fallback={
            <div className="panel-overlay">
              <div className="skeleton">Opening source page…</div>
            </div>
          }
        >
          <EvidencePanel
            evidence={selected}
            onClose={() => setSelected(null)}
          />
        </React.Suspense>
      )}
      {exportOpen && (
        <ExportModal docs={sourceDocs} onClose={() => setExportOpen(false)} />
      )}
      {upload && (
        <UploadModal
          maxUploadMb={ready.max_upload_mb ?? 100}
          companies={[
            ...new Set(docs.filter((d) => !d.synthetic).map((d) => d.company)),
          ]}
          onClose={() => setUpload(false)}
          onDone={async (doc) => {
            setUpload(false);
            changeSource(doc.synthetic ? "samples" : "uploaded");
            setCompany(doc.company);
            setView("reports");
            setNotice(
              "Report uploaded. It is being prepared for search. This page updates automatically.",
            );
            await refresh();
          }}
        />
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);
