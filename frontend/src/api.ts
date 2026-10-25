export interface RuntimeInfo {
  answer_provider: string;
  max_upload_mb: number;
}
export interface Document {
  id: string;
  title: string;
  company: string;
  document_type: string;
  period_start: string;
  period_end: string;
  publication_date: string | null;
  source_url: string | null;
  currency: string;
  units: string | null;
  basis: string;
  synthetic: boolean;
  status: string;
  warning: string | null;
  page_count: number;
  job: {
    id: string;
    status: string;
    attempts: number;
    error: string | null;
  } | null;
}
export interface Evidence {
  id: string;
  document_id: string;
  title: string;
  company: string;
  page_index: number;
  text: string;
  synthetic: boolean;
  period_end?: string;
  period_start?: string;
  kind?: string;
  printed_label?: string | null;
  source_url?: string | null;
}
export interface Fact {
  id: string;
  company: string;
  document_id: string;
  chunk_id: string;
  metric: string;
  value: string;
  units: string;
  currency: string;
  period_start: string;
  period_end: string;
  basis: string;
  revision: string;
  verified: boolean;
  page_index: number;
  title: string;
  source_text: string;
  synthetic: boolean;
  review_note: string | null;
}
export interface Calculation {
  result: string;
  units: string;
  formula: string;
  company?: string;
  citation_ids?: string[];
  citations?: Evidence[];
  normalised_inputs: { first: string; second: string };
  input_values: {
    value: string;
    currency: string;
    units: string;
    basis: string;
    revision: string;
    period: { fiscal: string; calendar: string };
  }[];
}
export interface Answer {
  run_id: string;
  mode: string;
  answer_kind?: "answer" | "report_overview" | "clarification" | "help";
  summary?: string;
  report_overviews?: {
    document_id: string;
    title: string;
    company: string;
    document_type: string;
    period_start: string;
    period_end: string;
    page_count: number;
    synthetic: boolean;
    citation_id: string;
  }[];
  suggestions?: string[];
  claims: { text: string; citation_ids: string[]; kind: string }[];
  evidence: Evidence[];
  calculations: Calculation[];
  abstained: boolean;
  limitation: string;
  latency_ms: number;
  cost_usd: number | null;
  configuration: Record<string, unknown>;
  usage: Record<string, unknown>;
}
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const r = await fetch("/api" + path, options);
  if (!r.ok) {
    let message = `Request failed (${r.status}). Please try again.`;
    try {
      const d = await r.json();
      if (typeof d.detail === "string") message = d.detail;
    } catch {}
    throw new Error(message);
  }
  return r.json() as Promise<T>;
}
export const post = <T>(path: string, data: unknown) =>
  api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
export function period(date: string) {
  const d = new Date(date + "T00:00:00");
  return `Q${Math.floor(((d.getMonth() + 9) % 12) / 3) + 1} FY${String(d.getFullYear() + (d.getMonth() >= 3 ? 1 : 0)).slice(-2)}`;
}
export function number(value: string) {
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 4 });
}

export function reportPeriod(start: string | undefined, end: string) {
  if (start) {
    const startYear = Number(start.slice(0, 4)),
      endYear = Number(end.slice(0, 4));
    if (start.slice(5) === "04-01" && end === `${startYear + 1}-03-31`)
      return `FY ${startYear}–${String(endYear).slice(-2)}`;
    const quarters: { [key: string]: string } = {
      "06-30": `${endYear}-04-01`,
      "09-30": `${endYear}-07-01`,
      "12-31": `${endYear}-10-01`,
      "03-31": `${endYear}-01-01`,
    };
    if (quarters[end.slice(5)] !== start) {
      const format = (d: string) =>
        new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
          day: "numeric",
          month: "short",
          year: "numeric",
        });
      return `${format(start)} – ${format(end)}`;
    }
  }
  return period(end);
}
