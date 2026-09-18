import "./MetricStrip.css";

function MetricStrip({ metrics = {}, loading = false }) {
  const items = [
    {
      id: "files",
      label: "Parsed Files",
      value: metrics.parsedFiles,
      icon: "description",
      description: "Source modules in repository AST",
    },
    {
      id: "symbols",
      label: "AST Symbols",
      value: metrics.astSymbols,
      icon: "code_blocks",
      description: "Functions, classes, and types",
    },
    {
      id: "nodes",
      label: "Graph Nodes",
      value: metrics.graphNodes,
      icon: "hub",
      description: "Structural code entities",
    },
    {
      id: "relationships",
      label: "Relationships",
      value: metrics.relationships,
      icon: "account_tree",
      description: "Resolved imports, calls & refs",
    },
  ];

  return (
    <div className="metric-strip-grid">
      {items.map((item) => {
        const hasValue = item.value !== null && item.value !== undefined && !Number.isNaN(item.value);
        const displayValue = loading
          ? "..."
          : hasValue
          ? Number(item.value).toLocaleString()
          : "—";

        return (
          <div className="metric-card" key={item.id}>
            <div className="metric-card-header">
              <span className="metric-label">{item.label}</span>
              <span className="material-symbols-outlined metric-icon">
                {item.icon}
              </span>
            </div>

            <div className="metric-value-row">
              <span className={`metric-value ${!hasValue && !loading ? "empty" : ""}`}>
                {displayValue}
              </span>
            </div>

            <span className="metric-description">{item.description}</span>
          </div>
        );
      })}
    </div>
  );
}

export default MetricStrip;
