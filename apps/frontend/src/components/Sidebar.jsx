import { useState } from "react";
import { useUser, UserButton } from "@clerk/react";
import RepositorySelectorDropdown from "./RepositorySelectorDropdown.jsx";
import "./Sidebar.css";

function Sidebar({
  activeView = "overview",
  onViewChange,
  repositories = [],
  selectedRepo = null,
  activeRepo = null,
  connectedReposCount = 0,
  onSelectRepository,
  mobileOpen = false,
  onCloseMobile,
}) {
  const { user, isLoaded } = useUser();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const currentRepo = activeRepo || selectedRepo;
  const isConnectedToGitHub = connectedReposCount > 0 || !!currentRepo;

  function handleNav(viewKey) {
    if (onViewChange) {
      onViewChange(viewKey);
    }
    if (onCloseMobile) {
      onCloseMobile();
    }
  }

  const isIntelligenceActive = [
    "intelligence",
    "architecture",
    "files",
    "graph",
    "dependencies",
    "apimap",
  ].includes(activeView);

  return (
    <>
      {/* Mobile Drawer Backdrop */}
      <div
        className={`sidebar-backdrop ${mobileOpen ? "active" : ""}`}
        onClick={onCloseMobile}
        aria-hidden="true"
      />

      <aside className={`codeai-sidebar ${mobileOpen ? "sidebar-mobile-open" : ""}`}>
        {/* Brand Header */}
        <div className="sidebar-header">
          <div className="sidebar-brand-wrapper">
            <div className="sidebar-brand-logo">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <div className="sidebar-brand-text">
              <span className="sidebar-brand-name" data-testid="brand-title">
                CodeAI
              </span>
              <span className="sidebar-brand-badge">Intelligence</span>
            </div>
          </div>

          <button
            type="button"
            className="sidebar-close-btn"
            onClick={onCloseMobile}
            aria-label="Close sidebar"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Workspace Selector */}
        <div className="sidebar-workspace">
          <button
            type="button"
            className={`workspace-pill ${dropdownOpen ? "workspace-pill--active" : ""}`}
            onClick={() => setDropdownOpen((prev) => !prev)}
            title="Switch workspace or repository"
            aria-haspopup="listbox"
            aria-expanded={dropdownOpen}
          >
            <div className="workspace-pill-left">
              <span className="material-symbols-outlined workspace-pill-icon">
                deployed_code
              </span>
              <span className="workspace-pill-name">
                {currentRepo
                  ? `${currentRepo.owner || "repo"}/${currentRepo.name}`
                  : "Select Repository"}
              </span>
            </div>
            <span className="material-symbols-outlined workspace-pill-chevron">
              {dropdownOpen ? "expand_less" : "unfold_more"}
            </span>
          </button>

          {dropdownOpen && (
            <RepositorySelectorDropdown
              className="dropdown--sidebar"
              repositories={repositories}
              activeRepo={currentRepo}
              onSelect={(repo) => {
                if (onSelectRepository) onSelectRepository(repo);
                setDropdownOpen(false);
              }}
              onConnect={() => {
                handleNav("repos");
                setDropdownOpen(false);
              }}
              onClose={() => setDropdownOpen(false)}
            />
          )}
        </div>

        {/* Main Navigation */}
        <nav className="sidebar-nav">
          <div className="sidebar-nav-section-title">Navigation</div>

          <button
            type="button"
            className={`sidebar-nav-item ${activeView === "overview" ? "active" : ""}`}
            onClick={() => handleNav("overview")}
          >
            <span className="material-symbols-outlined sidebar-nav-icon">
              dashboard
            </span>
            <span className="sidebar-nav-label">Overview</span>
          </button>

          <button
            type="button"
            className={`sidebar-nav-item ${activeView === "repos" ? "active" : ""}`}
            onClick={() => handleNav("repos")}
          >
            <span className="material-symbols-outlined sidebar-nav-icon">
              folder_open
            </span>
            <span className="sidebar-nav-label">Repositories</span>
          </button>

          <div className="sidebar-nav-section-title">Repository Intelligence</div>

          <button
            type="button"
            className={`sidebar-nav-item ${isIntelligenceActive ? "active" : ""}`}
            onClick={() => handleNav("intelligence")}
          >
            <span className="material-symbols-outlined sidebar-nav-icon">
              account_tree
            </span>
            <span className="sidebar-nav-label">Repository Intelligence</span>
          </button>

          {/* Sub-navigation for Intelligence */}
          <div className="sidebar-subnav">
            <button
              type="button"
              className={`sidebar-subnav-item ${activeView === "architecture" ? "active" : ""}`}
              onClick={() => handleNav("architecture")}
            >
              <span className="material-symbols-outlined sidebar-nav-icon">
                layers
              </span>
              <span className="sidebar-nav-label">Architecture</span>
            </button>

            <button
              type="button"
              className={`sidebar-subnav-item ${activeView === "files" ? "active" : ""}`}
              onClick={() => handleNav("files")}
            >
              <span className="material-symbols-outlined sidebar-nav-icon">
                description
              </span>
              <span className="sidebar-nav-label">Files</span>
            </button>

            <button
              type="button"
              className={`sidebar-subnav-item ${activeView === "graph" ? "active" : ""}`}
              onClick={() => handleNav("graph")}
            >
              <span className="material-symbols-outlined sidebar-nav-icon">
                hub
              </span>
              <span className="sidebar-nav-label">Code Graph</span>
            </button>

            <button
              type="button"
              className={`sidebar-subnav-item ${activeView === "dependencies" ? "active" : ""}`}
              onClick={() => handleNav("dependencies")}
            >
              <span className="material-symbols-outlined sidebar-nav-icon">
                lan
              </span>
              <span className="sidebar-nav-label">Dependencies</span>
            </button>

            <button
              type="button"
              className={`sidebar-subnav-item ${activeView === "apimap" ? "active" : ""}`}
              onClick={() => handleNav("apimap")}
            >
              <span className="material-symbols-outlined sidebar-nav-icon">
                api
              </span>
              <span className="sidebar-nav-label">API Map</span>
            </button>
          </div>

          <div className="sidebar-nav-section-title">Developer Workstation</div>

          <button
            type="button"
            className={`sidebar-nav-item ${activeView === "assistant" || activeView === "analysis" ? "active" : ""}`}
            onClick={() => handleNav("assistant")}
          >
            <span className="material-symbols-outlined sidebar-nav-icon">
              auto_awesome
            </span>
            <span className="sidebar-nav-label">AI Assistant</span>
          </button>

          <button
            type="button"
            className={`sidebar-nav-item ${activeView === "review" ? "active" : ""}`}
            onClick={() => handleNav("review")}
          >
            <span className="material-symbols-outlined sidebar-nav-icon">
              rate_review
            </span>
            <span className="sidebar-nav-label">Code Review</span>
          </button>

          <button
            type="button"
            className={`sidebar-nav-item ${activeView === "learning" ? "active" : ""}`}
            onClick={() => handleNav("learning")}
          >
            <span className="material-symbols-outlined sidebar-nav-icon">
              school
            </span>
            <span className="sidebar-nav-label">Learning</span>
          </button>

          <div className="sidebar-nav-section-title">System</div>

          <button
            type="button"
            className={`sidebar-nav-item ${activeView === "settings" ? "active" : ""}`}
            onClick={() => handleNav("settings")}
          >
            <span className="material-symbols-outlined sidebar-nav-icon">
              settings
            </span>
            <span className="sidebar-nav-label">Settings</span>
          </button>
        </nav>

        {/* Footer User Area */}
        <div className="sidebar-footer">
          {/* GitHub Connection Status */}
          <div
            className={`sidebar-github-status ${isConnectedToGitHub ? "connected" : ""}`}
          >
            <span className="sidebar-status-dot" />
            <span>
              {isConnectedToGitHub
                ? "Connected to GitHub"
                : "GitHub: Not connected"}
            </span>
          </div>

          {/* User Information & Clerk UserButton */}
          <div className="sidebar-user-row">
            <div className="sidebar-user-info">
              <span className="sidebar-user-name">
                {isLoaded && user
                  ? user.fullName || user.username || "Developer"
                  : "Loading user..."}
              </span>
              <span className="sidebar-user-email">
                {isLoaded && user
                  ? user.primaryEmailAddress?.emailAddress || "Active Session"
                  : "Authenticated"}
              </span>
            </div>

            <UserButton
              appearance={{
                elements: {
                  userButtonAvatarBox: {
                    width: "32px",
                    height: "32px",
                    borderRadius: "6px",
                    border: "1px solid var(--border-subtle)",
                  },
                  userButtonPopoverCard: {
                    backgroundColor: "var(--bg-surface-low)",
                    border: "1px solid var(--border-subtle)",
                    color: "var(--text-primary)",
                  },
                },
              }}
            />
          </div>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
