import "./ArchitectureOverview.css";

const ROLE_DISPLAY_NAMES = {
  REPOSITORY_ROLE: "REPOSITORY",
};

const CONCEPTUAL_LAYERS = [
  {
    id: "PRESENTATION",
    name: "PRESENTATION",
    description: "UI components and client state hooks",
    roles: ["COMPONENT", "HOOK"],
  },
  {
    id: "APPLICATION",
    name: "APPLICATION",
    description: "API route handlers, controllers, and services",
    roles: ["ROUTE", "CONTROLLER", "SERVICE"],
  },
  {
    id: "DOMAIN",
    name: "DOMAIN",
    description: "Core business logic, entities, and models",
    roles: ["MODEL", "ENTITY", "SERVICE"],
  },
  {
    id: "DATA",
    name: "DATA",
    description: "Database repositories and persistence schemas",
    roles: ["REPOSITORY", "REPOSITORY_ROLE", "MODEL"],
  },
  {
    id: "INFRASTRUCTURE",
    name: "INFRASTRUCTURE",
    description: "Auth/error middleware, shared utilities & config",
    roles: ["MIDDLEWARE", "UTILITY", "CONFIG", "ENTRYPOINT"],
  },
  {
    id: "TESTING",
    name: "TESTING",
    description: "Test specifications and test harnesses",
    roles: ["TEST"],
  },
];

const FLOW_STEPS = [
  { id: "PRESENTATION", name: "PRESENTATION", roles: "Components, Hooks" },
  { id: "APPLICATION", name: "APPLICATION", roles: "Routes, Controllers" },
  { id: "DOMAIN", name: "DOMAIN", roles: "Services, Models" },
  { id: "DATA", name: "DATA", roles: "Repositories, DB Schemas" },
];

function ArchitectureOverview({
  graphData = null,
  selectedRole = null,
  onSelectRole,
  selectedLayer = null,
  onSelectLayer,
}) {
  const nodes = Array.isArray(graphData?.nodes) ? graphData.nodes : [];

  // Compute actual counts for each role present in graph nodes
  const roleCounts = {};

  for (const node of nodes) {
    const rawRole =
      node.architecture_role ||
      node.metadata?.role ||
      (node.id?.startsWith("architecture:") ? node.id.split(":")[2] : null) ||
      node.type;

    if (!rawRole) continue;

    const normalized = (ROLE_DISPLAY_NAMES[rawRole.toUpperCase()] || rawRole).toUpperCase();
    const validRoles = [
      "CONTROLLER",
      "SERVICE",
      "REPOSITORY",
      "MODEL",
      "ENTITY",
      "COMPONENT",
      "HOOK",
      "ROUTE",
      "MIDDLEWARE",
      "UTILITY",
      "CONFIG",
      "ENTRYPOINT",
      "TEST",
    ];

    if (validRoles.includes(normalized)) {
      roleCounts[normalized] = (roleCounts[normalized] || 0) + 1;
    }
  }

  const detectedRoleEntries = Object.entries(roleCounts).sort((a, b) => b[1] - a[1]);

  return (
    <div className="arch-overview-container">
      {/* 1. Detected Architecture Roles */}
      <div className="arch-card">
        <div className="arch-card-header">
          <div className="arch-card-title-group">
            <span className="material-symbols-outlined arch-card-icon">
              verified
            </span>
            <span className="arch-card-title">Detected Architecture Roles</span>
          </div>
          <span className="arch-card-badge font-mono">
            {detectedRoleEntries.length} roles verified in AST
          </span>
        </div>

        {detectedRoleEntries.length === 0 ? (
          <p className="arch-layer-empty">
            Architecture roles will appear once repository static analysis is completed.
          </p>
        ) : (
          <div className="arch-roles-grid">
            {detectedRoleEntries.map(([role, count]) => {
              const isSelected = selectedRole === role;
              return (
                <button
                  type="button"
                  key={role}
                  className={`arch-role-pill-btn ${isSelected ? "active" : ""}`}
                  onClick={() => onSelectRole && onSelectRole(isSelected ? null : role)}
                  title={`Filter files classified as ${role}`}
                >
                  <span className="role-pill-name">{role}</span>
                  <span className="role-pill-count">{count}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 2. Conceptual Architecture Layers */}
      <div className="arch-card">
        <div className="arch-card-header">
          <div className="arch-card-title-group">
            <span className="material-symbols-outlined arch-card-icon">
              layers
            </span>
            <span className="arch-card-title">Architecture Layers</span>
          </div>
          <span className="arch-card-badge font-mono">
            System Tier Breakdown
          </span>
        </div>

        <div className="arch-layers-grid">
          {CONCEPTUAL_LAYERS.map((layer) => {
            const isSelected = selectedLayer === layer.id;
            const matchingRoles = layer.roles.filter(
              (r) => (roleCounts[r] || 0) > 0,
            );
            const totalCount = layer.roles.reduce(
              (sum, r) => sum + (roleCounts[r] || 0),
              0,
            );
            const hasData = matchingRoles.length > 0;

            return (
              <div
                key={layer.id}
                className={`arch-layer-card ${isSelected ? "active" : ""}`}
                onClick={() =>
                  onSelectLayer && onSelectLayer(isSelected ? null : layer.id)
                }
              >
                <div className="arch-layer-header">
                  <span className="arch-layer-name">{layer.name}</span>
                  <span className="arch-layer-count">
                    {hasData ? `${totalCount} symbols` : "—"}
                  </span>
                </div>

                <p className="arch-layer-desc">{layer.description}</p>

                {hasData ? (
                  <div className="arch-layer-roles">
                    {matchingRoles.map((role) => (
                      <span
                        key={role}
                        className="role-badge"
                        style={{
                          fontSize: 10,
                          padding: "1px 5px",
                          background: "var(--bg-surface-high)",
                          color: "var(--text-secondary)",
                          border: "1px solid var(--border-hairline)",
                        }}
                      >
                        {role} ({roleCounts[role]})
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="arch-layer-empty">
                    No detected components
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Architecture Flow Pipeline */}
      <div className="arch-card">
        <div className="arch-card-header">
          <div className="arch-card-title-group">
            <span className="material-symbols-outlined arch-card-icon">
              account_tree
            </span>
            <span className="arch-card-title">Architecture Flow</span>
          </div>
          <span className="arch-card-badge font-mono">
            Conceptual Tier Pipeline
          </span>
        </div>

        <div className="arch-flow-wrapper">
          {FLOW_STEPS.map((step, idx) => {
            const hasData =
              (CONCEPTUAL_LAYERS.find((l) => l.id === step.id)?.roles || []).some(
                (r) => (roleCounts[r] || 0) > 0,
              );

            return (
              <div key={step.id} style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
                <div className={`arch-flow-node ${hasData ? "active" : ""}`}>
                  <span className="arch-flow-node-title">{step.name}</span>
                  <span className="arch-flow-node-roles">{step.roles}</span>
                </div>

                {idx < FLOW_STEPS.length - 1 && (
                  <div className="arch-flow-arrow">
                    <span className="material-symbols-outlined">
                      arrow_forward
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default ArchitectureOverview;
