import { ArrowRight, GitBranch } from "lucide-react";
import "./RepositoryOverviewCard.css";

const STANDARD_LAYERS = [
  { name: "Presentation", roles: ["COMPONENT", "HOOK"] },
  { name: "Application", roles: ["ROUTE", "CONTROLLER"] },
  { name: "Domain", roles: ["SERVICE", "MODEL"] },
  { name: "Data", roles: ["REPOSITORY", "MODEL"] },
  { name: "Infrastructure", roles: ["MIDDLEWARE", "UTILITY"] },
  { name: "Testing", roles: ["TEST"] },
];

function fileRole(node) {
  const raw = node.architecture_role || node.metadata?.role;
  return raw ? String(raw).toUpperCase() : null;
}

function RepositoryOverviewCard({
  repo,
  status = "Not analyzed",
  roles = [],
  graphData = null,
  onExploreIntelligence,
  onExploreGraph,
}) {
  if (!repo) return null;

  const lower = status.toLowerCase();
  const isComplete = lower.includes("complete") || lower.includes("done");
  const roleSet = new Set(roles.map((r) => r.toUpperCase()));

  // Count files per tier from real file nodes (when the graph is loaded)
  const fileNodes = Array.isArray(graphData?.nodes)
    ? graphData.nodes.filter((n) => n.type === "file")
    : [];
  const totalFiles = fileNodes.length;
  const filesByRole = {};
  let unclassified = 0;
  for (const node of fileNodes) {
    const role = fileRole(node);
    if (!role) {
      unclassified += 1;
      continue;
    }
    filesByRole[role] = (filesByRole[role] || 0) + 1;
  }
  const hasCounts = totalFiles > 0;

  const tiers = STANDARD_LAYERS.map((layer) => {
    const activeRoles = layer.roles.filter((r) => roleSet.has(r));
    const files = layer.roles.reduce((sum, r) => sum + (filesByRole[r] || 0), 0);
    const share = hasCounts ? Math.round((files / totalFiles) * 100) : null;
    return { ...layer, activeRoles, files, share, isActive: activeRoles.length > 0 };
  });
  const presentTiers = tiers.filter((t) => t.isActive).length;

  const fullName = repo.owner ? `${repo.owner}/${repo.name}` : repo.name;

  return (
    <section className="repo-console-card" aria-label={`Repository ${fullName}`}>
      <div className="repo-console-head">
        <div className="repo-console-crumbs">
          {repo.owner && (
            <>
              <span className="repo-console-owner">{repo.owner}</span>
              <span className="repo-console-sep">/</span>
            </>
          )}
          <b>{repo.name}</b>
          <span className="repo-console-branch">
            <GitBranch size={12} />
            {repo.defaultBranch || "main"}
          </span>
          <span className={`repo-console-status ${isComplete ? "complete" : ""}`}>
            <span className="repo-console-dot" />
            {status}
          </span>
        </div>

        <div className="repo-console-actions">
          <button type="button" className="ws-btn ws-btn-secondary" onClick={onExploreGraph}>
            CodeGraph
          </button>
          <button type="button" className="ws-btn ws-btn-primary" onClick={onExploreIntelligence}>
            Open intelligence
            <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {roles.length === 0 ? (
        <p className="repo-console-empty">
          Architecture tiers appear here after the repository is analyzed.
        </p>
      ) : (
        <div className="repo-console-table-wrap">
          <table className="repo-console-table">
            <thead>
              <tr>
                <th>Tier</th>
                <th>Roles detected</th>
                {hasCounts && <th className="repo-console-share-col">Share of files</th>}
                {hasCounts && <th className="num">Files</th>}
              </tr>
            </thead>
            <tbody>
              {tiers.map((tier) => (
                <tr key={tier.name} className={tier.isActive ? "" : "off"}>
                  <td>{tier.name}</td>
                  <td className="mono">
                    {tier.isActive ? tier.activeRoles.map((r) => r.toLowerCase()).join(", ") : "—"}
                  </td>
                  {hasCounts && (
                    <td>
                      <span className="repo-console-bar" title={`${tier.share}% of files`}>
                        <i style={{ width: `${Math.min(tier.share, 100)}%` }} />
                      </span>
                    </td>
                  )}
                  {hasCounts && <td className="num">{tier.files.toLocaleString()}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {roles.length > 0 && (
        <div className="repo-console-foot">
          <span>
            {roles.length} {roles.length === 1 ? "role" : "roles"} detected
          </span>
          <span>
            {presentTiers} of {STANDARD_LAYERS.length} tiers present
          </span>
          {hasCounts && unclassified > 0 && (
            <span>{unclassified.toLocaleString()} files unclassified</span>
          )}
        </div>
      )}
    </section>
  );
}

export default RepositoryOverviewCard;
