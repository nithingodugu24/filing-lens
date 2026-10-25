import { useEffect, useRef, useState } from "react";
import { Network } from "vis-network";
import { DataSet } from "vis-data";
import { api, post, type Document, type Evidence } from "./api";
type Entity = {
  id: string;
  text: string;
  type: string;
  page_index: number;
  count: number;
  mentions: { page_index: number; sentence: string }[];
};
type Graph = {
  nodes: Entity[];
  edges: { id: string; from: string; to: string; label: string }[];
  enabled: boolean;
  status: string;
  error: string | null;
  limitation: string;
};
const colors: Record<string, string> = {
  COMPANY: "#4779cf",
  PERSON: "#168264",
  MONEY: "#b97a20",
  METRIC: "#9b5fc0",
  DATE: "#66758c",
  PERCENTAGE: "#d16f42",
};
export function KnowledgeGraph({
  docs,
  onEvidence,
}: {
  docs: Document[];
  onEvidence: (e: Evidence) => void;
}) {
  const [docId, setDocId] = useState(
      docs.find((d) => d.status === "indexed")?.id ?? "",
    ),
    [data, setData] = useState<Graph | null>(null),
    [type, setType] = useState("all"),
    [selected, setSelected] = useState<Entity | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const container = useRef<HTMLDivElement>(null),
    network = useRef<Network | null>(null);
  const load = () =>
    docId
      ? api<Graph>(`/documents/${docId}/knowledge-graph`)
          .then(setData)
          .catch((e) => setError(e.message))
      : Promise.resolve();
  useEffect(() => {
    setData(null);
    setSelected(null);
    void load();
  }, [docId]);
  useEffect(() => {
    if (!data || !["queued", "processing"].includes(data.status)) return;
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
  }, [docId, data?.status]);
  useEffect(() => {
    if (!container.current || !data?.nodes.length) return;
    const nodes = data.nodes
        .filter((n) => type === "all" || type === n.type)
        .slice(0, 150),
      ids = new Set(nodes.map((n) => n.id));
    const instance = new Network(
      container.current,
      {
        nodes: new DataSet(
          nodes.map((n) => ({
            id: n.id,
            label: n.text.length > 36 ? n.text.slice(0, 33) + "…" : n.text,
            color: colors[n.type] || "#66758c",
            font: { color: "#ffffff" },
            shape: "dot",
            size: 12 + Math.min(15, n.count),
          })),
        ),
        edges: new DataSet(
          data.edges
            .filter((e) => ids.has(e.from) && ids.has(e.to))
            .slice(0, 350),
        ),
      },
      {
        physics: { stabilization: { iterations: 100 } },
        interaction: { navigationButtons: true, keyboard: true },
        edges: { font: { size: 9 }, color: "#a5b3c2" },
      },
    );
    network.current = instance;
    instance.on("selectNode", (event) =>
      setSelected(data.nodes.find((n) => n.id === event.nodes[0]) ?? null),
    );
    return () => {
      instance.destroy();
      network.current = null;
    };
  }, [data, type]);
  const doc = docs.find((d) => d.id === docId);
  return (
    <section className="knowledge-view">
      <div className="graph-controls">
        <label>
          Report
          <select value={docId} onChange={(e) => setDocId(e.target.value)}>
            {docs
              .filter((d) => d.status === "indexed")
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
          </select>
        </label>
        <label>
          Show names and figures
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="all">All types</option>
            {Object.keys(colors).map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {data?.error && <p role="alert">{data.error}</p>}
      <p>{data?.limitation}</p>
      {!data?.enabled ? (
        <p className="sample-notice">
          Optional feature: enable entity extraction and install the English
          language model on the server.
        </p>
      ) : (
        <button
          className="button secondary"
          disabled={busy || ["queued", "processing"].includes(data.status)}
          onClick={async () => {
            setBusy(true);
            try {
              await post(`/documents/${docId}/extract-entities`, {});
              await load();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {["queued", "processing"].includes(data.status)
            ? "Finding names and figures…"
            : "Extract names and figures"}
        </button>
      )}
      {data?.nodes.length ? (
        <>
          <div
            className="graph-canvas"
            aria-label="Entity relationships"
            ref={container}
          />
          <p>
            Drag to pan, scroll to zoom, or choose a name below. The graph
            displays up to 150 nodes and 350 edges.
          </p>
          <div className="entity-list">
            {data.nodes
              .filter((n) => type === "all" || type === n.type)
              .slice(0, 150)
              .map((n) => (
                <button
                  className="citation"
                  key={n.id}
                  onClick={() => {
                    setSelected(n);
                    network.current?.focus(n.id, { scale: 1.4 });
                  }}
                >
                  {n.text} · {n.count}
                </button>
              ))}
          </div>
        </>
      ) : (
        <div className="empty-state">No extracted entities yet.</div>
      )}
      {selected && doc && (
        <article className="note-card">
          <h2>{selected.text}</h2>
          <p>
            {selected.type} · {selected.count} mentions
          </p>
          {selected.mentions.map((m, i) => (
            <div key={i}>
              <p>{m.sentence}</p>
              <button
                className="citation"
                onClick={() =>
                  onEvidence({
                    id: selected.id,
                    document_id: doc.id,
                    title: doc.title,
                    company: doc.company,
                    page_index: m.page_index,
                    text: m.sentence,
                    highlightText: selected.text,
                    synthetic: doc.synthetic,
                  })
                }
              >
                Open page {m.page_index + 1}
              </button>
            </div>
          ))}
        </article>
      )}
    </section>
  );
}
