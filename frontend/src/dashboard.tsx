import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import { api, number, reportPeriod } from "./api";
import { SentimentCharts } from "./sentiment";

interface Trend {
  basis: string;
  revision: string;
  company: string;
  period_start: string;
  period_end: string;
  value: string;
  normalised_value?: string;
  currency: string;
  units: string;
  series: string;
}
interface Analytics {
  summary: {
    document_count: number;
    company_count: number;
    fact_count: number;
  };
  revenue_trends: Trend[];
  margin_trends: Trend[];
  company_profiles: {
    company: string;
    document_count: number;
    fact_count: number;
    latest_revenue: string | null;
    latest_margin: string | null;
    revenue_growth: string | null;
    metric_coverage: number;
  }[];
  excluded_ambiguous_facts: number;
}
const colors = ["#168264", "#4779cf", "#b97a20", "#9b5fc0"];
function chartData(rows: Trend[], revenue = false) {
  const series = [...new Set(rows.map((r) => r.series))];
  const data = [...new Set(rows.map((r) => r.period_end))]
    .sort()
    .map((date) => ({
      period: reportPeriod(
        rows.find((r) => r.period_end === date)?.period_start,
        date,
      ),
      ...Object.fromEntries(
        rows
          .filter((r) => r.period_end === date)
          .map((r) => [
            r.series,
            Number(revenue ? r.normalised_value : r.value),
          ]),
      ),
    }));
  return { series, data };
}
export function Dashboard({
  synthetic,
  documentIds,
}: {
  synthetic: boolean;
  documentIds: string[];
}) {
  const selectedIds = documentIds.join(",");
  const [data, setData] = useState<Analytics | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setData(null);
    api<Analytics>(
      `/analytics?synthetic=${synthetic}&document_ids=${encodeURIComponent(selectedIds)}`,
    )
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [synthetic, selectedIds]);
  if (error)
    return (
      <p role="alert" className="error">
        {error}
      </p>
    );
  if (!data)
    return (
      <div className="skeleton" role="status">
        Loading checked figures…
      </div>
    );
  const revenue = chartData(data.revenue_trends, true),
    margin = chartData(data.margin_trends);
  const latest = data.revenue_trends.at(-1),
    latestMargin = data.margin_trends.at(-1);
  const profiles = data.company_profiles.filter((p) => p.fact_count > 0);
  const radar = [
    "Revenue growth",
    "Operating margin",
    "Reports",
    "Metric coverage",
  ].map((metric, i) => ({
    metric,
    ...Object.fromEntries(
      profiles.map((p) => {
        const raw = [
          Number(p.revenue_growth ?? 0),
          Number(p.latest_margin ?? 0),
          p.document_count,
          p.metric_coverage,
        ][i];
        const max = Math.max(
          1,
          ...profiles.map((v) =>
            Math.abs(
              [
                Number(v.revenue_growth ?? 0),
                Number(v.latest_margin ?? 0),
                v.document_count,
                v.metric_coverage,
              ][i],
            ),
          ),
        );
        return [p.company, Math.max(0, (raw / max) * 100)];
      }),
    ),
  }));
  return (
    <section className="dashboard" aria-label="Financial dashboard">
      <p className="context-explanation">
        {synthetic ? "Made-up sample data." : "Your uploaded reports."} Charts
        use only figures marked source checked. Different currencies, reporting
        lengths and accounting bases stay in separate series.
      </p>
      <div className="kpi-grid">
        {[
          ["Reports ready", data.summary.document_count],
          ["Companies", data.summary.company_count],
          [
            "Latest revenue",
            latest
              ? `${latest.company} · ${number(latest.value)} ${latest.currency} ${latest.units}`
              : "No checked figures",
          ],
          [
            "Latest operating margin",
            latestMargin
              ? `${latestMargin.company} · ${latestMargin.value}%`
              : "No checked figures",
          ],
        ].map(([label, value]) => (
          <article className="kpi-card" key={label}>
            <small>{label}</small>
            <strong>{value}</strong>
            <span>
              {label === "Latest revenue" && latest
                ? reportPeriod(latest.period_start, latest.period_end)
                : label === "Latest operating margin" && latestMargin
                  ? reportPeriod(
                      latestMargin.period_start,
                      latestMargin.period_end,
                    )
                  : ""}
            </span>
          </article>
        ))}
      </div>
      {!data.summary.fact_count ? (
        <div className="empty-state">
          <h2>No checked financial figures yet</h2>
          <p>
            Open Compare numbers to review extracted figures. You can also
            select Sample reports above to explore the charts.
          </p>
        </div>
      ) : (
        <div className="chart-grid">
          <article className="chart-card">
            <h2>Revenue over time</h2>
            <p>
              Amounts shown in crore; the original value remains available in
              Compare numbers.
            </p>
            <ResponsiveContainer width="100%" height={310}>
              <LineChart data={revenue.data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" />
                <YAxis />
                <Tooltip />
                <Legend />
                {revenue.series.map((s, i) => (
                  <Line
                    isAnimationActive={false}
                    key={s}
                    name={s}
                    type="linear"
                    dataKey={s}
                    stroke={colors[i % 4]}
                    strokeWidth={2}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </article>
          <article className="chart-card">
            <h2>Operating margin</h2>
            <p>
              Percentage of revenue. Check basis and period before comparing.
            </p>
            <ResponsiveContainer width="100%" height={310}>
              <BarChart data={margin.data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" />
                <YAxis unit="%" />
                <Tooltip formatter={(v) => `${v}%`} />
                <Legend />
                {margin.series.map((s, i) => (
                  <Bar
                    key={s}
                    dataKey={s}
                    fill={colors[i % 4]}
                    isAnimationActive={false}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </article>
          {profiles.length >= 2 && (
            <article className="chart-card company-profile">
              <h2>Company comparison</h2>
              <p>
                Relative scale: highest company on each axis = 100. Missing or
                negative growth displays as 0. This is a visual comparison, not
                an investment score.
              </p>
              <ResponsiveContainer width="100%" height={330}>
                <RadarChart data={radar}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="metric" />
                  <PolarRadiusAxis
                    domain={[0, 100]}
                    tick={false}
                    axisLine={false}
                  />
                  <Tooltip />
                  <Legend />
                  {profiles.map((p, i) => (
                    <Radar
                      isAnimationActive={false}
                      key={p.company}
                      name={p.company}
                      dataKey={p.company}
                      stroke={colors[i % 4]}
                      fill={colors[i % 4]}
                      fillOpacity={0.12}
                    />
                  ))}
                </RadarChart>
              </ResponsiveContainer>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Growth</th>
                      <th>Margin</th>
                      <th>Reports</th>
                      <th>Coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profiles.map((p) => (
                      <tr key={p.company}>
                        <td>{p.company}</td>
                        <td>
                          {p.revenue_growth === null
                            ? "Unavailable"
                            : number(p.revenue_growth) + "%"}
                        </td>
                        <td>{p.latest_margin ?? "Unavailable"}%</td>
                        <td>{p.document_count}</td>
                        <td>{p.metric_coverage}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          )}
        </div>
      )}
      {data.excluded_ambiguous_facts > 0 && (
        <p>
          Some duplicate or ambiguous facts were excluded. Review them before
          plotting.
        </p>
      )}
      <SentimentCharts synthetic={synthetic} documentIds={documentIds} />
    </section>
  );
}
