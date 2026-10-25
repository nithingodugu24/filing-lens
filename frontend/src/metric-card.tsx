import { ArrowUpRight, FileText } from "lucide-react";
import { number, reportPeriod, type MetricAnswer, type Evidence } from "./api";

export function MetricCard({
  metric: m,
  evidence,
  onEvidence,
}: {
  metric: MetricAnswer;
  evidence?: Evidence;
  onEvidence: (e: Evidence) => void;
}) {
  return (
    <article className="metric-card">
      <div className="metric-label">{m.label}</div>
      <div className="metric-amount">
        {m.currency === "INR"
          ? "₹"
          : m.currency === "PCT"
            ? ""
            : m.currency + " "}
        {number(m.value)} <span>{m.units === "percent" ? "%" : m.units}</span>
      </div>
      <p>
        {m.company} · {reportPeriod(m.period_start, m.period_end)} · {m.basis}
      </p>
      {m.change_percent !== null && (
        <div className="metric-change">
          <ArrowUpRight size={16} /> {Number(m.change_percent) > 0 ? "+" : ""}
          {number(m.change_percent)}% year on year{" "}
          <span>
            from {m.currency === "INR" ? "₹" : ""}
            {number(m.previous_value!)} {m.units}
          </span>
        </div>
      )}
      <div className="metric-source">
        <small>
          {m.verification_method === "automatic"
            ? "Source row and totals checked automatically"
            : "Source row reviewed"}
        </small>
        {evidence && (
          <button
            className="citation"
            onClick={() =>
              onEvidence({
                ...evidence,
                highlightText: m.label.replace(/\s+\d[\d,\s]*$/, ""),
              })
            }
          >
            <FileText size={15} /> PDF page {m.source_page}
          </button>
        )}
      </div>
    </article>
  );
}
