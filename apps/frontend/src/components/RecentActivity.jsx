import "./RecentActivity.css";

function RecentActivity({ activities = [], onViewAll }) {
  function formatRelative(dateStr) {
    if (!dateStr) return "—";
    try {
      const d = new Date(dateStr);
      if (Number.isNaN(d.getTime())) return "—";
      return d.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch {
      return "—";
    }
  }

  return (
    <div className="recent-activity-card">
      <div className="recent-activity-header">
        <span className="recent-activity-title">Recent Repository Activity</span>
        {onViewAll && activities.length > 0 && (
          <button
            type="button"
            className="ws-btn ws-btn-ghost"
            style={{ fontSize: 11, padding: "4px 8px" }}
            onClick={onViewAll}
          >
            View Repositories →
          </button>
        )}
      </div>

      {activities.length === 0 ? (
        <p className="activity-empty">No recent repository activity</p>
      ) : (
        <div className="recent-activity-list">
          {activities.slice(0, 5).map((act, idx) => {
            const sha = act.commitSha?.slice(0, 7) || act.sha?.slice(0, 7) || null;
            return (
              <div
                className="recent-activity-item"
                key={act.id || act.commitSha || idx}
              >
                <div className="activity-left">
                  <div className={`activity-badge ${act.type === "sync" ? "sync" : ""}`}>
                    <span className="material-symbols-outlined">
                      {act.type === "sync" ? "sync" : "commit"}
                    </span>
                  </div>

                  <div className="activity-details">
                    <span className="activity-message">
                      {act.message || act.title || "Repository snapshot recorded"}
                    </span>
                    <div className="activity-meta">
                      <span>{act.repositoryName || "Repository"}</span>
                      {sha && <span className="activity-sha">{sha}</span>}
                      <span>·</span>
                      <span>{formatRelative(act.committedAt || act.createdAt)}</span>
                    </div>
                  </div>
                </div>

                <div className="activity-right">
                  {(act.realFileCount !== undefined || act.fileCount !== undefined) && (
                    <div className="activity-stats">
                      <span>{act.realFileCount ?? act.fileCount} files</span>
                      {(act.realAdditions !== undefined || act.additions !== undefined) && (
                        <span className="addition">
                          +{act.realAdditions ?? act.additions}
                        </span>
                      )}
                      {(act.realDeletions !== undefined || act.deletions !== undefined) && (
                        <span className="deletion">
                          -{act.realDeletions ?? act.deletions}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default RecentActivity;
