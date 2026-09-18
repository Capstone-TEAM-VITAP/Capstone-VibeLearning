import { useEffect, useRef, useState } from "react";
import "./RepositorySelectorDropdown.css";

export default function RepositorySelectorDropdown({
  repositories = [],
  activeRepo = null,
  onSelect,
  onConnect,
  onClose,
  className = "",
}) {
  const [filter, setFilter] = useState("");
  const dropdownRef = useRef(null);

  // Close on Escape or click outside
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape") {
        onClose();
      }
    }

    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [onClose]);

  const filteredRepos = repositories.filter((repo) => {
    if (!filter.trim()) return true;
    const q = filter.toLowerCase();
    const fullName = repo.owner ? `${repo.owner}/${repo.name}` : repo.name;
    return fullName.toLowerCase().includes(q);
  });

  return (
    <div
      className={`repo-selector-popover ${className}`}
      ref={dropdownRef}
      role="dialog"
      aria-label="Select Repository"
    >
      {/* Popover Header */}
      <div className="repo-popover-header">
        <span className="repo-popover-title">SELECT REPOSITORY</span>
        <span className="repo-popover-count font-mono">
          {repositories.length} connected
        </span>
      </div>

      {/* Filter Input if multiple repos */}
      {repositories.length > 4 && (
        <div className="repo-popover-search">
          <span className="material-symbols-outlined search-icon">search</span>
          <input
            type="text"
            className="repo-popover-input font-mono"
            placeholder="Filter repositories..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            autoFocus
          />
          {filter && (
            <button
              type="button"
              className="search-clear-btn"
              onClick={() => setFilter("")}
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          )}
        </div>
      )}

      {/* Repositories List */}
      <div className="repo-popover-list" role="listbox">
        {repositories.length === 0 ? (
          <div className="repo-popover-empty">
            <span className="material-symbols-outlined empty-icon">folder_off</span>
            <div className="empty-title">No repositories connected</div>
            <div className="empty-sub">
              Connect a GitHub repository to begin repository analysis.
            </div>
          </div>
        ) : filteredRepos.length === 0 ? (
          <div className="repo-popover-no-match font-mono">
            No repositories matching "{filter}"
          </div>
        ) : (
          filteredRepos.map((repo) => {
            const isActive = activeRepo?.id === repo.id;
            const fullName = repo.owner ? `${repo.owner}/${repo.name}` : repo.name;
            const branch = repo.defaultBranch || repo.branch || "main";

            return (
              <button
                key={repo.id}
                type="button"
                className={`repo-popover-item ${isActive ? "active" : ""}`}
                onClick={() => onSelect(repo)}
                role="option"
                aria-selected={isActive}
              >
                <div className="repo-item-status-col">
                  {isActive ? (
                    <span className="material-symbols-outlined repo-check-icon">
                      check
                    </span>
                  ) : (
                    <span className="repo-item-dot" />
                  )}
                </div>

                <div className="repo-item-info">
                  <div className="repo-item-name font-mono" title={fullName}>
                    {fullName}
                  </div>
                  <div className="repo-item-meta">
                    <span className="repo-item-branch font-mono">
                      <span className="material-symbols-outlined branch-icon">
                        call_split
                      </span>
                      {branch}
                    </span>
                    {repo.status && (
                      <span className="repo-item-badge font-mono">
                        {repo.status}
                      </span>
                    )}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Popover Footer */}
      <div className="repo-popover-footer">
        <button
          type="button"
          className="repo-popover-connect-btn"
          onClick={onConnect}
        >
          <span className="material-symbols-outlined">add</span>
          <span>Connect Repository</span>
        </button>
      </div>
    </div>
  );
}
