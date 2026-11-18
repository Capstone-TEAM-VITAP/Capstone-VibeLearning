import "./MetricStrip.css";

function formatRelative(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return null;
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days} d ago`;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function formatDelta(n) {
  if (n === null || n === undefined || Number.isNaN(n) || n === 0) return null;
  const abs = Math.abs(n);
  const text = abs >= 1000 ? `${(abs / 1000).toFixed(1)}k` : abs.toLocaleString();
  return `${n > 0 ? "+" : "−"}${text}`;
}

/**
 * Slim, single-row metric bar (Dense console style).
 * `deltas` is optional: { parsedFiles, astSymbols, graphNodes, relationships }.
 */
function MetricStrip({ metrics = {}, deltas = {}, lastSnapshotAt = null, loading = false }) {
  const items = [
    { id: "parsedFiles", label: "files", title: "Source files parsed into the AST" },
    { id: "astSymbols", label: "symbols", title: "Functions, classes and types" },
    { id: "graphNodes", label: "nodes", title: "Structural code entities in the graph" },
    { id: "relationships", label: "edges", title: "Resolved imports, calls and references" },
  ];

  const snapshotText = formatRelative(lastSnapshotAt);

  return (
    <div className="metric-bar" aria-busy={loading}>
      {items.map((item) => {
        const value = metrics[item.id];
        const hasValue = value !== null && value !== undefined && !Number.isNaN(value);
        const delta = formatDelta(deltas[item.id]);
        return (
          <div className="metric-bar-stat" key={item.id} title={item.title}>
            <b className={`metric-bar-value ${!hasValue && !loading ? "empty" : ""}`}>
              {loading ? "…" : hasValue ? Number(value).toLocaleString() : "—"}
            </b>
            <span className="metric-bar-label">{item.label}</span>
            {delta && !loading && (
              <em className={`metric-bar-delta ${deltas[item.id] < 0 ? "down" : ""}`}>{delta}</em>
            )}
          </div>
        );
      })}

      {snapshotText && (
        <div className="metric-bar-sync">
          <span className="metric-bar-dot" />
          Last snapshot {snapshotText}
        </div>
      )}
    </div>
  );
}

export default MetricStrip;
