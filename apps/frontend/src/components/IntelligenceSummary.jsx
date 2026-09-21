import "./IntelligenceSummary.css";

function IntelligenceSummary({ graphData = null, loading = false }) {
  const nodes = Array.isArray(graphData?.nodes) ? graphData.nodes : [];
  const edges = Array.isArray(graphData?.edges) ? graphData.edges : [];
  const hasData = graphData !== null && graphData.schema_version === "1.0";

  const filesCount = hasData
    ? nodes.filter((n) => n.type?.toLowerCase() === "file").length
    : null;

  const symbolsCount = hasData
    ? nodes.filter((n) =>
        ["function", "class", "method", "variable", "constant"].includes(
          n.type?.toLowerCase(),
        ),
      ).length
    : null;

  const graphNodesCount = hasData ? nodes.length : null;
  const relationshipsCount = hasData ? edges.length : null;

  const metrics = [
    {
      id: "files",
      label: "Parsed Files",
      value: filesCount,
      icon: "description",
      subtext: "Source files analyzed in AST",
    },
    {
      id: "symbols",
      label: "AST Symbols",
      value: symbolsCount,
      icon: "code_blocks",
      subtext: "Functions, classes, methods & variables",
    },
    {
      id: "nodes",
      label: "Graph Nodes",
      value: graphNodesCount,
      icon: "hub",
      subtext: "Deterministic Graph IR 1.0 entities",
    },
    {
      id: "relationships",
      label: "Relationships",
      value: relationshipsCount,
      icon: "account_tree",
      subtext: "Imports, calls, and structural edges",
    },
  ];

  return (
    <div className="intel-summary-container">
      {metrics.map((item) => {
        const hasVal = item.value !== null && item.value !== undefined && !Number.isNaN(item.value);
        const displayVal = loading
          ? "..."
          : hasVal
          ? Number(item.value).toLocaleString()
          : "—";

        return (
          <div className="intel-summary-card" key={item.id}>
            <div className="intel-summary-header">
              <span className="intel-summary-label">{item.label}</span>
              <span className="material-symbols-outlined intel-summary-icon">
                {item.icon}
              </span>
            </div>

            <div className="intel-summary-value-row">
              <span
                className={`intel-summary-value ${!hasVal && !loading ? "empty" : ""}`}
              >
                {displayVal}
              </span>
            </div>

            <span className="intel-summary-subtext">{item.subtext}</span>
          </div>
        );
      })}
    </div>
  );
}

export default IntelligenceSummary;
