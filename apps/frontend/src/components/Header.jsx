import { useState } from "react";
import { UserButton } from "@clerk/react";
import RepositorySelectorDropdown from "./RepositorySelectorDropdown.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import "./Header.css";

function Header({
  repositories = [],
  activeRepo = null,
  selectedRepo = null,
  repository = null,
  branch = null,
  analysisStatus = null,
  onSelectRepository,
  onConnectRepository,
  onSearchClick,
  onToggleMobileSidebar,
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const currentRepo = activeRepo || selectedRepo;

  const repoName = currentRepo
    ? (currentRepo.owner ? `${currentRepo.owner}/${currentRepo.name}` : currentRepo.name)
    : (typeof repository === "object" && repository !== null
        ? (repository.name || (repository.owner ? `${repository.owner}/${repository.name}` : "No repository selected"))
        : (repository || "No repository selected"));

  const branchDisplay = branch || currentRepo?.defaultBranch || "—";
  const statusDisplay = analysisStatus || "Not analyzed";

  const isStatusComplete = statusDisplay.toLowerCase().includes("complete") || statusDisplay.toLowerCase().includes("done");
  const isStatusBusy = statusDisplay.toLowerCase().includes("analyz") || statusDisplay.toLowerCase().includes("in_progress") || statusDisplay.toLowerCase().includes("running");

  return (
    <header className="codeai-header">
      {/* Mobile Hamburger Menu Toggle */}
      <button
        type="button"
        className="header-menu-btn"
        onClick={onToggleMobileSidebar}
        aria-label="Toggle navigation menu"
      >
        <span className="material-symbols-outlined">menu</span>
      </button>

      {/* Left: Repository & Branch Context */}
      <div className="header-context-cluster">
        {/* Repository Context (Interactive Selector) */}
        <div className="header-repo-dropdown-wrap">
          <button
            type="button"
            className={`header-meta-pill header-meta-pill--interactive ${dropdownOpen ? "header-meta-pill--open" : ""}`}
            onClick={() => setDropdownOpen((prev) => !prev)}
            title="Switch active repository"
            aria-haspopup="listbox"
            aria-expanded={dropdownOpen}
          >
            <span className="material-symbols-outlined header-meta-icon">
              folder_open
            </span>
            <span className="header-meta-text">{repoName}</span>
            <span className="material-symbols-outlined header-chevron-icon">
              {dropdownOpen ? "expand_less" : "expand_more"}
            </span>
          </button>

          {dropdownOpen && (
            <RepositorySelectorDropdown
              className="dropdown--header"
              repositories={repositories}
              activeRepo={currentRepo}
              onSelect={(repo) => {
                if (onSelectRepository) onSelectRepository(repo);
                setDropdownOpen(false);
              }}
              onConnect={() => {
                if (onConnectRepository) onConnectRepository();
                setDropdownOpen(false);
              }}
              onClose={() => setDropdownOpen(false)}
            />
          )}
        </div>

        <span className="header-separator">/</span>

        {/* Branch Context */}
        <div className="header-meta-pill branch-pill" title={`Branch: ${branchDisplay}`}>
          <span className="material-symbols-outlined header-meta-icon">
            call_split
          </span>
          <span className="header-meta-text">{branchDisplay}</span>
        </div>

        {/* Analysis Status Indicator */}
        <div
          className={`header-status-pill ${
            isStatusComplete
              ? "status-complete"
              : isStatusBusy
              ? "status-busy"
              : ""
          }`}
          title={`Status: ${statusDisplay}`}
        >
          <span className="header-status-dot" />
          <span>{statusDisplay}</span>
        </div>
      </div>

      {/* Right: Actions & User */}
      <div className="header-actions-cluster">
        {/* Command / Search Trigger */}
        <button
          type="button"
          className="header-search-btn"
          onClick={onSearchClick}
          title="Search repository code, symbols, and architecture"
        >
          <span className="material-symbols-outlined header-search-icon">
            search
          </span>
          <span className="header-search-text">Search</span>
          <kbd className="header-search-kbd">Ctrl K</kbd>
        </button>

        {/* Theme Toggle (Light / Dark) */}
        <ThemeToggle />

        {/* Clerk User Button */}
        <UserButton
          appearance={{
            elements: {
              userButtonAvatarBox: {
                width: "30px",
                height: "30px",
                borderRadius: "6px",
                border: "1px solid var(--border-subtle)",
              },
            },
          }}
        />
      </div>
    </header>
  );
}

export default Header;
