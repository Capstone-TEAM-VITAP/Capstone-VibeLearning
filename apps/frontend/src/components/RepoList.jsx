function RepoList({ repos, selectedId, busyId, onSelect, onSync, onDelete }) {
  if (!repos.length) {
    return (
      <p className="repo-empty" data-testid="repo-list-empty">
        No repositories connected yet. Paste a GitHub URL above to start.
      </p>
    );
  }

  return (
    <ul className="repo-list" data-testid="repo-list">
      {repos.map((repo) => (
        <li
          key={repo.id}
          className={`repo-item${repo.id === selectedId ? " repo-item-selected" : ""}`}
          data-testid={`repo-item-${repo.id}`}
        >
          <button className="repo-item-main" type="button" onClick={() => onSelect(repo.id)}>
            <span className="repo-item-name">
              {repo.owner}/{repo.name}
            </span>
            <span className="repo-item-meta">
              {repo.defaultBranch} · {repo.lastSyncSha ? repo.lastSyncSha.slice(0, 7) : "never synced"}
            </span>
          </button>
          <div className="repo-item-actions">
            <button
              className="btn-sign-in"
              type="button"
              disabled={busyId === repo.id}
              onClick={() => onSync(repo.id)}
              data-testid={`repo-sync-${repo.id}`}
            >
              {busyId === repo.id ? "Syncing…" : "Sync"}
            </button>
            <button
              className="btn-danger"
              type="button"
              disabled={busyId === repo.id}
              onClick={() => onDelete(repo.id)}
              data-testid={`repo-delete-${repo.id}`}
            >
              Remove
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default RepoList;
