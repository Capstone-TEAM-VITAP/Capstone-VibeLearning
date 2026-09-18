import "./RepositoryOverviewCard.css";

const ROLE_CSS_CLASS = {
  COMPONENT: "role-badge-component",
  HOOK: "role-badge-hook",
  ROUTE: "role-badge-route",
  CONTROLLER: "role-badge-controller",
  SERVICE: "role-badge-service",
  REPOSITORY: "role-badge-repository",
  MODEL: "role-badge-model",
  MIDDLEWARE: "role-badge-middleware",
  UTILITY: "role-badge-utility",
  ENTRYPOINT: "role-badge-entrypoint",
  TEST: "role-badge-test",
};

const STANDARD_LAYERS = [
  { name: "Presentation", roles: ["COMPONENT", "HOOK"] },
  { name: "Application", roles: ["ROUTE", "CONTROLLER"] },
  { name: "Domain", roles: ["SERVICE", "MODEL"] },
  { name: "Data", roles: ["REPOSITORY", "MODEL"] },
  { name: "Infrastructure", roles: ["MIDDLEWARE", "UTILITY"] },
  { name: "Testing", roles: ["TEST"] },
];

function RepositoryOverviewCard({
  repo,
  status = "Not analyzed",
  roles = [],
  onExploreIntelligence,
  onExploreGraph,
}) {
  if (!repo) return null;

  const isComplete = status.toLowerCase().includes("complete") || status.toLowerCase().includes("done");
  const hasRoles = Array.isArray(roles) && roles.length > 0;

  return (
    <div className="repo-intelligence-card">
      {/* Header */}
      <div className="repo-intelligence-header">
        <div className="repo-intelligence-title-group">
          <span className="repo-intelligence-eyebrow">
            Primary Repository Intelligence
          </span>
          <div className="repo-intelligence-name-row">
            <span className="repo-intelligence-name">
              {repo.owner ? `${repo.owner}/${repo.name}` : repo.name}
            </span>
            <span className="repo-intelligence-branch">
              <span className="material-symbols-outlined" style={{ fontSize: 13 }}>
                call_split
              </span>
              {repo.defaultBranch || "main"}
            </span>
          </div>
        </div>

        <div className={`repo-intelligence-status-badge ${isComplete ? "complete" : ""}`}>
          <span className="status-dot" />
          <span>{status}</span>
        </div>
      </div>

      {/* Architecture Roles Section */}
      <div className="repo-architecture-section">
        <div className="architecture-section-title">
          <span>Detected Architecture Roles</span>
          {hasRoles && (
            <span className="font-mono text-muted" style={{ fontSize: 11 }}>
              {roles.length} roles verified
            </span>
          )}
        </div>

        {hasRoles ? (
          <div className="architecture-roles-wrap">
            {roles.map((role) => {
              const roleKey = role.toUpperCase();
              const badgeClass = ROLE_CSS_CLASS[roleKey] || "role-badge-utility";
              return (
                <span key={roleKey} className={`role-badge ${badgeClass}`}>
                  <span className="material-symbols-outlined" style={{ fontSize: 12 }}>
                    check
                  </span>
                  {roleKey}
                </span>
              );
            })}
          </div>
        ) : (
          <p className="architecture-empty">
            Architecture data will appear after repository analysis.
          </p>
        )}
      </div>

      {/* Architecture Layers Strip */}
      <div className="repo-architecture-section">
        <div className="architecture-section-title">
          <span>Architecture Tiers</span>
        </div>

        <div className="architecture-layers-grid">
          {STANDARD_LAYERS.map((layer) => {
            const activeRoles = layer.roles.filter((r) => roles.includes(r));
            const isActive = activeRoles.length > 0;

            return (
              <div
                key={layer.name}
                className={`layer-box ${isActive ? "active" : ""}`}
                title={
                  isActive
                    ? `Active roles: ${activeRoles.join(", ")}`
                    : "No detected symbols in this tier"
                }
              >
                <span className="layer-name">{layer.name}</span>
                <span className="layer-roles">
                  {isActive ? activeRoles.join(", ") : "—"}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="repo-intelligence-actions">
        <button
          type="button"
          className="ws-btn ws-btn-primary"
          onClick={onExploreIntelligence}
        >
          <span className="material-symbols-outlined">account_tree</span>
          Explore Repository Intelligence
        </button>

        <button
          type="button"
          className="ws-btn ws-btn-secondary"
          onClick={onExploreGraph}
        >
          <span className="material-symbols-outlined">hub</span>
          Explore CodeGraph
        </button>
      </div>
    </div>
  );
}

export default RepositoryOverviewCard;
