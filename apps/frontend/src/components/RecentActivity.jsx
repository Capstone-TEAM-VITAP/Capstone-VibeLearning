import "./RecentActivity.css";

function formatAgo(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d`;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function RecentActivity({ activities = [], onViewAll, limit = 6 }) {
  return (
    <section className="console-card activity-log">
      <div className="console-card-head">
        <h2 className="console-card-title">Recent activity</h2>
        {onViewAll && activities.length > 0 && (
          <button type="button" className="ws-btn ws-btn-ghost" onClick={onViewAll}>
            View repositories
          </button>
        )}
      </div>

      {activities.length === 0 ? (
        <p className="activity-log-empty">No repository activity yet.</p>
      ) : (
        <ul className="activity-log-list">
          {activities.slice(0, limit).map((act, idx) => {
            const sha = act.commitSha?.slice(0, 7) || act.sha?.slice(0, 7) || null;
            const when = act.committedAt || act.createdAt;
            const files = act.realFileCount ?? act.fileCount;
            const adds = act.realAdditions ?? act.additions;
            const dels = act.realDeletions ?? act.deletions;
            // All zeros means the stats are unknown, not an empty commit
            const hasStats = Boolean(files || adds || dels);
            return (
              <li key={act.id || act.commitSha || idx}>
                <time dateTime={when || undefined} title={when ? new Date(when).toLocaleString() : ""}>
                  {formatAgo(when)}
                </time>
                <div className="activity-log-body">
                  <span className="activity-log-msg">
                    {act.message || act.title || "Snapshot recorded"}
                  </span>
                  <span className="activity-log-meta">
                    {act.repositoryName && <span>{act.repositoryName}</span>}
                    {sha && <code>{sha}</code>}
                    {hasStats && <span>{files ?? 0} files</span>}
                    {hasStats && <span className="add">+{adds ?? 0}</span>}
                    {hasStats && <span className="del">−{dels ?? 0}</span>}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default RecentActivity;
