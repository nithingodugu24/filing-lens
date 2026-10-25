import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
  Legend,
} from "recharts";
import { api, post } from "./api";

type Result = {
  enabled: boolean;
  status: string;
  error: string | null;
  result: {
    overall_sentiment: string;
    confidence: number;
    analyzed_at: string;
    section_sentiments: {
      section: string;
      page_index: number;
      sentiment: string;
      confidence: number;
      key_phrases: string[];
    }[];
  } | null;
};
export function Sentiment({
  documentId,
  onPage,
}: {
  documentId: string;
  onPage: (p: number) => void;
}) {
  const [data, setData] = useState<Result | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const load = () =>
    api<Result>(`/documents/${documentId}/sentiment`)
      .then(setData)
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
  }, [documentId]);
  useEffect(() => {
    if (data?.status !== "queued" && data?.status !== "processing") return;
    const timer = setInterval(load, 6000);
    return () => clearInterval(timer);
  }, [documentId, data?.status]);
  return (
    <section className="sentiment-panel">
      <h3>Management tone</h3>
      <p>
        FinBERT estimates the tone of identified management-commentary pages. A
        positive tone does not establish company performance.
      </p>
      {error && <p role="alert">{error}</p>}
      {data?.error && <p role="alert">{data.error}</p>}
      {!data?.enabled ? (
        <p className="sample-notice">
          Optional feature: enable sentiment analysis and install the ML models
          on the server.
        </p>
      ) : (
        <button
          className="button secondary"
          disabled={
            busy || data.status === "queued" || data.status === "processing"
          }
          onClick={async () => {
            setBusy(true);
            try {
              await post(`/documents/${documentId}/analyze-sentiment`, {});
              await load();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {data.status === "queued" || data.status === "processing"
            ? "Analysing commentary…"
            : data.result
              ? "Analyse again"
              : "Analyse commentary"}
        </button>
      )}
      {data?.result && (
        <>
          <h3 className={`sentiment-label ${data.result.overall_sentiment}`}>
            {data.result.overall_sentiment} ·{" "}
            {(data.result.confidence * 100).toFixed(1)}% model confidence
          </h3>
          <small>
            Analysed {new Date(data.result.analyzed_at).toLocaleString()}
          </small>
          {data.result.section_sentiments.map((s, i) => (
            <article className="note-card" key={i}>
              <strong>
                {s.section} · {s.sentiment}
              </strong>
              <p>{(s.confidence * 100).toFixed(1)}% confidence</p>
              {s.key_phrases.map((p, j) => (
                <p key={j}>{p}</p>
              ))}
              <button className="citation" onClick={() => onPage(s.page_index)}>
                Check page {s.page_index + 1}
              </button>
            </article>
          ))}
        </>
      )}
    </section>
  );
}
type Timeline = {
  document_id: string;
  company: string;
  period_end: string;
  sentiment: string;
  confidence: number;
  score: number;
};
export function SentimentCharts({
  synthetic,
  documentIds,
}: {
  synthetic: boolean;
  documentIds: string[];
}) {
  const [rows, setRows] = useState<Timeline[]>([]);
  useEffect(() => {
    api<Timeline[]>(`/sentiment?synthetic=${synthetic}`)
      .then(setRows)
      .catch(() => setRows([]));
  }, [synthetic]);
  const selectedRows = rows.filter((r) => documentIds.includes(r.document_id));
  const companies = [...new Set(selectedRows.map((r) => r.company))];
  const periods = [...new Set(selectedRows.map((r) => r.period_end))].sort();
  const points = periods.map((p) => ({
    period: p,
    ...Object.fromEntries(
      selectedRows
        .filter((r) => r.period_end === p)
        .map((r) => [r.company, r.score]),
    ),
  }));
  const latest = companies.map(
    (company) => selectedRows.filter((r) => r.company === company).at(-1)!,
  );
  return (
    <article className="chart-card">
      <h2>Management tone over time</h2>
      {!selectedRows.length ? (
        <p>
          No sentiment analysis yet. Open a report, choose Sentiment and analyse
          its management commentary.
        </p>
      ) : (
        <>
          <p>
            Scale: negative −1 to positive +1. Tone estimates from identified
            sections.
          </p>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={latest} layout="vertical">
              <XAxis type="number" domain={[-1, 1]} />
              <YAxis type="category" dataKey="company" />
              <Tooltip />
              <Bar dataKey="score" fill="#168264" />
            </BarChart>
          </ResponsiveContainer>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={points}>
              <XAxis dataKey="period" />
              <YAxis domain={[-1, 1]} />
              <Tooltip />
              <Legend />
              {companies.map((c, i) => (
                <Line
                  dataKey={c}
                  key={c}
                  stroke={i % 2 ? "#4779cf" : "#168264"}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </article>
  );
}
