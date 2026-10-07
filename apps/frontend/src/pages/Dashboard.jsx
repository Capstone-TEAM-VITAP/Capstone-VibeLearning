import { useEffect, useState } from "react";
import { useAuth } from "@clerk/react";
import {
  getCurrentUser,
  listRepos,
  listSnapshots,
  getChangedFiles,
  getDiff,
  getSnapshotGraph,
  syncRepo,
} from "../services/api.js";
import AnalysisDemo from "../components/AnalysisDemo.jsx";
import AIAssistant from "../components/AIAssistant.jsx";
import ReposSection from "../components/ReposSection.jsx";
import Sidebar from "../components/Sidebar.jsx";
import Header from "../components/Header.jsx";
import MetricStrip from "../components/MetricStrip.jsx";
import RepositoryOverviewCard from "../components/RepositoryOverviewCard.jsx";
import RecentActivity from "../components/RecentActivity.jsx";
import ArchitectureOverview from "../components/ArchitectureOverview.jsx";
import RepositoryTree from "../components/RepositoryTree.jsx";
import IntelligenceSummary from "../components/IntelligenceSummary.jsx";
import DependencyHealth from "../components/DependencyHealth.jsx";
import CodeGraphView from "../components/CodeGraphView.jsx";
import LearningView from "../components/LearningView.jsx";
import "./Dashboard.css";

const KNOWN_ROLES = [
  "COMPONENT",
  "HOOK",
  "ROUTE",
  "CONTROLLER",
  "SERVICE",
  "REPOSITORY",
  "MODEL",
  "MIDDLEWARE",
  "UTILITY",
  "ENTRYPOINT",
  "TEST",
];

function PlaceholderView({ title, description, icon, phase }) {
  return (
    <div className="workstation-placeholder">
      <div className="placeholder-icon-box">
        <span className="material-symbols-outlined">{icon}</span>
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
      <div className="placeholder-meta">
        <span className="placeholder-badge">
          <span className="material-symbols-outlined">schedule</span>
          Coming in {phase}
        </span>
        <span className="placeholder-badge">
          <span className="material-symbols-outlined">terminal</span>
          Terminal Horizon Workstation
        </span>
      </div>
    </div>
  );
}

function Dashboard() {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const [user, setUser] = useState(null);
  const [repos, setRepos] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [view, setView] = useState("overview");
  const [selectedRepoId, setSelectedRepoId] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [graphData, setGraphData] = useState(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState(null);
  const [syncingId, setSyncingId] = useState(null);
  const [refreshCount, setRefreshCount] = useState(0);

  // Filters and selection in Repository Intelligence workspace
  const [selectedRoleFilter, setSelectedRoleFilter] = useState(null);
  const [selectedLayerFilter, setSelectedLayerFilter] = useState(null);
  const [selectedTreePath, setSelectedTreePath] = useState(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    let isCancelled = false;

    Promise.resolve().then(async () => {
      try {
        const userResponse = await getCurrentUser(getToken);
        if (isCancelled) return;
        setUser(userResponse.data);

        const repoData = await listRepos(getToken);
        if (isCancelled) return;
        setRepos(repoData);

        if (repoData.length) {
          setSelectedRepoId((prev) => prev || repoData[0].id);
        }

        const allSnapshots = [];

        for (const repo of repoData) {
          try {
            const repoSnapshots = await listSnapshots(getToken, repo.id);

            for (const snapshot of repoSnapshots) {
              try {
                const files = await getChangedFiles(
                  getToken,
                  repo.id,
                  snapshot.commitSha,
                  snapshot.baseSha,
                );

                let diffData = null;
                try {
                  diffData = await getDiff(
                    getToken,
                    repo.id,
                    snapshot.commitSha,
                    snapshot.baseSha,
                  );
                } catch (error) {
                  console.warn("Could not load diff:", snapshot.commitSha, error);
                }

                allSnapshots.push({
                  ...snapshot,
                  repositoryId: repo.id,
                  repositoryName: `${repo.owner}/${repo.name}`,
                  realFileCount: files?.fileCount || files?.files?.length || 0,
                  realAdditions: diffData?.additions ?? snapshot.additions ?? 0,
                  realDeletions: diffData?.deletions ?? snapshot.deletions ?? 0,
                });
              } catch (error) {
                console.warn("Could not load snapshot details:", error);
                allSnapshots.push({
                  ...snapshot,
                  repositoryId: repo.id,
                  repositoryName: `${repo.owner}/${repo.name}`,
                  realFileCount: snapshot.fileCount || 0,
                  realAdditions: snapshot.additions || 0,
                  realDeletions: snapshot.deletions || 0,
                });
              }
            }
          } catch (error) {
            console.warn("Could not load snapshots for repo:", repo.id, error);
          }
        }

        if (!isCancelled) {
          setSnapshots(allSnapshots);
        }
      } catch (error) {
        console.error("Dashboard loading failed:", error);
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [isLoaded, isSignedIn, getToken, view, refreshCount]);

  // Selected Repository
  const selectedRepo = repos.find((r) => r.id === selectedRepoId) || repos[0] || null;
  const repoDisplayName = selectedRepo ? `${selectedRepo.owner}/${selectedRepo.name}` : null;
  const repoBranch = selectedRepo?.defaultBranch || (selectedRepo ? "main" : null);

  // Latest snapshot for selected repo
  const selectedRepoSnapshots = snapshots.filter(
    (s) => s.repositoryId === selectedRepo?.id,
  );
  const latestSelectedSnapshot = [...selectedRepoSnapshots].sort(
    (a, b) => new Date(b.committedAt || 0) - new Date(a.committedAt || 0),
  )[0];

  // Load Graph IR for active repo's latest snapshot
  useEffect(() => {
    let isCancelled = false;

    Promise.resolve().then(async () => {
      if (!selectedRepo?.id || !latestSelectedSnapshot?.commitSha) {
        if (!isCancelled) {
          setGraphLoading(false);
          setGraphData(null);
          setGraphError(null);
        }
        return;
      }

      try {
        setGraphLoading(true);
        setGraphError(null);
        const g = await getSnapshotGraph(
          getToken,
          selectedRepo.id,
          latestSelectedSnapshot.commitSha,
        );
        if (isCancelled) return;
        if (g && g.schema_version === "1.0") {
          setGraphData(g);
        } else {
          setGraphData(null);
        }
      } catch (err) {
        if (isCancelled) return;
        console.warn("Could not load graph IR:", err);
        setGraphData(null);
        setGraphError(err.message || "Failed to load graph IR");
      } finally {
        if (!isCancelled) {
          setGraphLoading(false);
        }
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [getToken, selectedRepo?.id, latestSelectedSnapshot?.commitSha, refreshCount]);

  // Ensure snapshots for selected repo are fetched if not present in memory
  useEffect(() => {
    let isCancelled = false;
    if (!isLoaded || !isSignedIn || !selectedRepo?.id) return;

    const hasSnapshots = snapshots.some((s) => s.repositoryId === selectedRepo.id);
    if (!hasSnapshots) {
      Promise.resolve().then(async () => {
        try {
          const repoSnaps = await listSnapshots(getToken, selectedRepo.id);
          if (isCancelled) return;
          if (Array.isArray(repoSnaps) && repoSnaps.length > 0) {
            const newItems = repoSnaps.map((s) => ({
              ...s,
              repositoryId: selectedRepo.id,
              repositoryName: `${selectedRepo.owner}/${selectedRepo.name}`,
              realFileCount: s.fileCount || 0,
              realAdditions: s.additions || 0,
              realDeletions: s.deletions || 0,
            }));
            setSnapshots((prev) => {
              const existingIds = new Set(prev.map((item) => item.id));
              const filtered = newItems.filter((item) => !existingIds.has(item.id));
              return [...prev, ...filtered];
            });
          }
        } catch (err) {
          console.warn("Could not load snapshots for switched repo:", selectedRepo.id, err);
        }
      });
    }

    return () => {
      isCancelled = true;
    };
  }, [isLoaded, isSignedIn, getToken, selectedRepo, snapshots]);

  const activeGraph =
    selectedRepo?.id && latestSelectedSnapshot?.commitSha ? graphData : null;

  // Derived Intelligence Metrics from real Graph IR or deterministic snapshot counts
  const parsedFilesCount = activeGraph?.nodes
    ? activeGraph.nodes.filter((n) => n.type === "file").length
    : latestSelectedSnapshot?.realFileCount ?? null;

  const astSymbolsCount = activeGraph?.nodes
    ? activeGraph.nodes.filter(
        (n) => n.type !== "file" && n.type !== "repository",
      ).length
    : null;

  const graphNodesCount = activeGraph?.nodes ? activeGraph.nodes.length : null;
  const relationshipsCount = activeGraph?.edges ? activeGraph.edges.length : null;

  const intelligenceMetrics = {
    parsedFiles: parsedFilesCount,
    astSymbols: astSymbolsCount,
    graphNodes: graphNodesCount,
    relationships: relationshipsCount,
  };

  // Extract detected architecture roles strictly from real graph nodes
  const detectedRoles = Array.isArray(activeGraph?.nodes)
    ? [
        ...new Set(
          activeGraph.nodes
            .map((n) => {
              if (n.architecture_role) return n.architecture_role.toUpperCase();
              const upperType = n.type?.toUpperCase();
              if (KNOWN_ROLES.includes(upperType)) return upperType;
              return null;
            })
            .filter(Boolean),
        ),
      ]
    : [];

  const analysisStatus =
    activeGraph && activeGraph.schema_version === "1.0"
      ? "Analysis Complete"
      : selectedRepoSnapshots.length > 0
      ? "Analysis Complete"
      : repos.length > 0
      ? "No analyzed snapshot"
      : null;

  // Centralized single-source-of-truth repository switcher
  function handleSelectRepository(repoOrId) {
    const targetRepo =
      typeof repoOrId === "object" && repoOrId !== null
        ? repoOrId
        : repos.find((r) => r.id === repoOrId);

    if (!targetRepo || targetRepo.id === selectedRepoId) return;

    // 1. Set active repo
    setSelectedRepoId(targetRepo.id);

    // 2. Immediately wipe stale graph data and mark loading
    setGraphData(null);
    setGraphError(null);
    setGraphLoading(true);

    // 3. Clear all filters and selected tree nodes
    setSelectedRoleFilter(null);
    setSelectedLayerFilter(null);
    setSelectedTreePath(null);
  }

  async function handleSyncRepo(repoId) {
    try {
      setSyncingId(repoId);
      await syncRepo(getToken, repoId);
      setRefreshCount((c) => c + 1);
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setSyncingId(null);
    }
  }

  const isIntelligenceView = ["intelligence", "architecture", "files", "dependencies"].includes(view);

  return (
    <div className="codeai-workstation-shell">
      {/* Google Stitch Terminal Horizon Sidebar */}
      <Sidebar
        activeView={view}
        onViewChange={(newView) => setView(newView)}
        repositories={repos}
        activeRepo={selectedRepo}
        selectedRepo={selectedRepo}
        connectedReposCount={repos.length}
        onSelectRepository={handleSelectRepository}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      {/* Main Workstation Container */}
      <div className={`codeai-main-container ${view === "graph" ? "codeai-main-container--graph" : ""}`}>
        {/* Google Stitch Terminal Horizon Header */}
        <Header
          repositories={repos}
          activeRepo={selectedRepo}
          selectedRepo={selectedRepo}
          repository={repoDisplayName}
          branch={repoBranch}
          analysisStatus={analysisStatus}
          onSelectRepository={handleSelectRepository}
          onConnectRepository={() => setView("repos")}
          onSearchClick={() => console.log("Search codebase clicked")}
          onToggleMobileSidebar={() => setMobileOpen((prev) => !prev)}
        />

        {/* Dynamic Page Content */}
        <main className={`codeai-page-content ${view === "graph" ? "codeai-page-content--fullbleed" : ""}`}>
          {/* =========================================================
             OVERVIEW DASHBOARD (PHASE 3)
             ========================================================= */}
          {view === "overview" && (
            <div className="overview-container">
              {/* Top Hero Section */}
              <div className="overview-hero">
                <span className="overview-eyebrow">
                  <span className="material-symbols-outlined">terminal</span>
                  Repository Intelligence
                </span>
                <h1 className="overview-title">Understand your codebase.</h1>
                <p className="overview-subtitle">
                  AI-powered repository intelligence for understanding, reviewing
                  and learning unfamiliar software.
                </p>

                <div className="overview-hero-actions">
                  <button
                    type="button"
                    className="ws-btn ws-btn-primary"
                    onClick={() => setView("repos")}
                  >
                    <span className="material-symbols-outlined">add_circle</span>
                    Connect Repository
                  </button>

                  <button
                    type="button"
                    className="ws-btn ws-btn-secondary"
                    onClick={() => setView("analysis")}
                  >
                    <span className="material-symbols-outlined">auto_awesome</span>
                    Ask AI
                  </button>
                </div>
              </div>

              {/* Four Compact Intelligence Metrics */}
              <MetricStrip metrics={intelligenceMetrics} loading={loading} />

              {/* Primary Repository Intelligence Card */}
              {selectedRepo && (
                <RepositoryOverviewCard
                  repo={selectedRepo}
                  status={analysisStatus || "Not analyzed"}
                  roles={detectedRoles}
                  onExploreIntelligence={() => setView("intelligence")}
                  onExploreGraph={() => setView("graph")}
                />
              )}

              {/* Connected Repositories Grid or Polished Empty State */}
              <div className="overview-section">
                <div className="overview-section-header">
                  <span className="overview-section-title">
                    Connected Repositories ({repos.length})
                  </span>
                  {repos.length > 0 && (
                    <button
                      type="button"
                      className="ws-btn ws-btn-ghost"
                      style={{ fontSize: 12 }}
                      onClick={() => setView("repos")}
                    >
                      Manage All Repositories →
                    </button>
                  )}
                </div>

                {repos.length === 0 ? (
                  <div className="overview-empty-repo">
                    <div className="overview-empty-icon">
                      <span className="material-symbols-outlined">folder_open</span>
                    </div>
                    <h3>No repositories connected</h3>
                    <p>
                      Connect a GitHub repository to begin building its structural
                      intelligence graph.
                    </p>
                    <button
                      type="button"
                      className="ws-btn ws-btn-primary"
                      onClick={() => setView("repos")}
                    >
                      <span className="material-symbols-outlined">add</span>
                      Connect Repository
                    </button>
                  </div>
                ) : (
                  <div className="overview-repo-grid">
                    {repos.map((repo) => {
                      const isSelected = repo.id === selectedRepo?.id;
                      const repoSnaps = snapshots.filter(
                        (s) => s.repositoryId === repo.id,
                      );
                      const latestSnap = [...repoSnaps].sort(
                        (a, b) =>
                          new Date(b.committedAt || 0) -
                          new Date(a.committedAt || 0),
                      )[0];
                      const isAnalyzed = repoSnaps.length > 0;
                      const isSyncing = syncingId === repo.id;

                      return (
                        <div
                          key={repo.id}
                          className={`overview-repo-card ${
                            isSelected ? "selected" : ""
                          }`}
                        >
                          <div className="overview-repo-header">
                            <div className="overview-repo-info">
                              <div className="overview-repo-icon">
                                <span className="material-symbols-outlined">
                                  deployed_code
                                </span>
                              </div>
                              <div className="overview-repo-text">
                                <span className="overview-repo-name">
                                  {repo.owner}/{repo.name}
                                </span>
                                <span className="overview-repo-meta">
                                  <span>GitHub</span>
                                  <span>·</span>
                                  <span>{repo.defaultBranch || "main"}</span>
                                </span>
                              </div>
                            </div>

                            <span
                              className={`overview-repo-status ${
                                isAnalyzed ? "complete" : ""
                              }`}
                            >
                              {isAnalyzed ? "Analysis Complete" : "Not analyzed"}
                            </span>
                          </div>

                          <div className="overview-repo-commit-info">
                            <span>Last snapshot:</span>
                            <code>
                              {latestSnap?.commitSha
                                ? latestSnap.commitSha.slice(0, 7)
                                : "—"}
                            </code>
                          </div>

                          <div className="overview-repo-actions">
                            <button
                              type="button"
                              className="ws-btn ws-btn-secondary"
                              style={{ padding: "4px 10px", fontSize: 12 }}
                              onClick={() => {
                                handleSelectRepository(repo);
                                setView("repos");
                              }}
                            >
                              Open
                            </button>

                            <button
                              type="button"
                              className="ws-btn ws-btn-secondary"
                              style={{ padding: "4px 10px", fontSize: 12 }}
                              onClick={() => {
                                handleSelectRepository(repo);
                                setView("analysis");
                              }}
                            >
                              Analyze
                            </button>

                            <button
                              type="button"
                              className="ws-btn ws-btn-ghost"
                              style={{ padding: "4px 8px", fontSize: 12 }}
                              onClick={() => handleSyncRepo(repo.id)}
                              disabled={isSyncing}
                            >
                              <span
                                className="material-symbols-outlined"
                                style={{
                                  fontSize: 14,
                                  animation: isSyncing
                                    ? "spin 1s linear infinite"
                                    : "none",
                                }}
                              >
                                sync
                              </span>
                              {isSyncing ? "Syncing..." : "Sync"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Recent Activity */}
              <div className="overview-section">
                <RecentActivity
                  activities={snapshots}
                  onViewAll={() => setView("repos")}
                />
              </div>

              {/* Quick Actions */}
              <div className="overview-section">
                <div className="overview-section-header">
                  <span className="overview-section-title">Quick Actions</span>
                </div>

                <div className="overview-quick-actions-grid">
                  <button
                    type="button"
                    className="quick-action-card"
                    onClick={() => setView("repos")}
                  >
                    <span className="material-symbols-outlined quick-action-icon">
                      folder_open
                    </span>
                    <div className="quick-action-text">
                      <span className="quick-action-label">Connect Repository</span>
                      <span className="quick-action-badge">Active</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="quick-action-card"
                    onClick={() => setView("analysis")}
                  >
                    <span className="material-symbols-outlined quick-action-icon">
                      troubleshoot
                    </span>
                    <div className="quick-action-text">
                      <span className="quick-action-label">Analyze Snapshot</span>
                      <span className="quick-action-badge">Active</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="quick-action-card"
                    onClick={() => setView("graph")}
                  >
                    <span className="material-symbols-outlined quick-action-icon">
                      hub
                    </span>
                    <div className="quick-action-text">
                      <span className="quick-action-label">Explore CodeGraph</span>
                      <span className="quick-action-badge">Active</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="quick-action-card"
                    onClick={() => setView("assistant")}
                  >
                    <span className="material-symbols-outlined quick-action-icon">
                      auto_awesome
                    </span>
                    <div className="quick-action-text">
                      <span className="quick-action-label">Ask AI</span>
                      <span className="quick-action-badge">Phase 7</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="quick-action-card"
                    onClick={() => setView("review")}
                  >
                    <span className="material-symbols-outlined quick-action-icon">
                      rate_review
                    </span>
                    <div className="quick-action-text">
                      <span className="quick-action-label">Code Review</span>
                      <span className="quick-action-badge">Phase 8</span>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* =========================================================
             REPOSITORIES
             ========================================================= */}
          {view === "repos" && (
            <section className="dashboard-content">
              <ReposSection getToken={getToken} />
            </section>
          )}

          {/* =========================================================
             AI ASSISTANT WORKSPACE
             ========================================================= */}
          {view === "assistant" && (
            <section className="dashboard-content">
              <AIAssistant
                getToken={getToken}
                selectedRepo={selectedRepo}
                latestSelectedSnapshot={latestSelectedSnapshot}
                graphData={activeGraph}
                setView={setView}
              />
            </section>
          )}

          {/* =========================================================
             CODE ANALYSIS DEMO
             ========================================================= */}
          {view === "analysis" && (
            <section className="dashboard-content">
              <AnalysisDemo getToken={getToken} />
            </section>
          )}

          {/* =========================================================
             REPOSITORY INTELLIGENCE WORKSPACE (PHASE 4 CORE)
             ========================================================= */}
          {isIntelligenceView && (
            <div className="intelligence-workspace">
              {/* Workspace Header */}
              <div className="intel-workspace-hero">
                <div className="intel-hero-top">
                  <div className="intel-hero-title-group">
                    <span className="intel-hero-eyebrow">
                      <span className="material-symbols-outlined">terminal</span>
                      Repository Intelligence
                    </span>
                    <h1 className="intel-hero-title">Repository Intelligence</h1>
                    <p className="intel-hero-desc">
                      Explore the structure, architecture, and relationships inside your codebase.
                    </p>
                  </div>

                  <div className="intel-hero-actions">
                    <button
                      type="button"
                      className="ws-btn ws-btn-secondary"
                      onClick={() => setView("analysis")}
                    >
                      <span className="material-symbols-outlined">auto_awesome</span>
                      Ask AI
                    </button>

                    <button
                      type="button"
                      className="ws-btn ws-btn-secondary"
                      onClick={() => setView("graph")}
                    >
                      <span className="material-symbols-outlined">hub</span>
                      Explore CodeGraph
                    </button>

                    <button
                      type="button"
                      className="ws-btn ws-btn-secondary"
                      onClick={() => setView("repos")}
                    >
                      <span className="material-symbols-outlined">difference</span>
                      Analyze Changes
                    </button>
                  </div>
                </div>

                {/* Repository Context Cluster */}
                <div className="intel-meta-cluster">
                  <div className="intel-meta-tag">
                    <span className="material-symbols-outlined" style={{ fontSize: 13 }}>
                      folder_open
                    </span>
                    <span>Repository: <strong>{selectedRepo ? `${selectedRepo.owner}/${selectedRepo.name}` : "—"}</strong></span>
                  </div>

                  <div className="intel-meta-tag">
                    <span className="material-symbols-outlined" style={{ fontSize: 13 }}>
                      call_split
                    </span>
                    <span>Branch: <strong>{repoBranch || "—"}</strong></span>
                  </div>

                  <div className="intel-meta-tag">
                    <span className="material-symbols-outlined" style={{ fontSize: 13 }}>
                      commit
                    </span>
                    <span>Commit: <strong>{latestSelectedSnapshot?.commitSha ? latestSelectedSnapshot.commitSha.slice(0, 7) : "—"}</strong></span>
                  </div>

                  <div className="intel-meta-tag">
                    <span
                      className="status-dot"
                      style={{
                        backgroundColor: activeGraph ? "var(--status-success)" : "var(--text-muted)",
                      }}
                    />
                    <span>Status: <strong>{analysisStatus || "Not analyzed"}</strong></span>
                  </div>
                </div>
              </div>

              {/* Fallback States */}
              {!selectedRepo ? (
                <div className="intel-notice-card">
                  <div className="intel-notice-icon">
                    <span className="material-symbols-outlined">folder_off</span>
                  </div>
                  <h3>No repository selected</h3>
                  <p>Select or connect a repository to inspect its architectural intelligence.</p>
                  <button
                    type="button"
                    className="ws-btn ws-btn-primary"
                    onClick={() => setView("repos")}
                  >
                    Open Repositories
                  </button>
                </div>
              ) : graphLoading ? (
                <div className="intel-notice-card">
                  <div className="intel-notice-icon">
                    <span
                      className="material-symbols-outlined"
                      style={{ animation: "spin 1.2s linear infinite" }}
                    >
                      sync
                    </span>
                  </div>
                  <h3>Loading repository intelligence...</h3>
                  <p>Fetching canonical Graph IR 1.0 AST nodes and relationships.</p>
                </div>
              ) : graphError ? (
                <div className="intel-notice-card">
                  <div className="intel-notice-icon" style={{ color: "var(--status-error)" }}>
                    <span className="material-symbols-outlined">error</span>
                  </div>
                  <h3>Repository intelligence could not be loaded</h3>
                  <p>{graphError}</p>
                  <button
                    type="button"
                    className="ws-btn ws-btn-secondary"
                    onClick={() => setRefreshCount((c) => c + 1)}
                  >
                    Retry
                  </button>
                </div>
              ) : !activeGraph ? (
                <div className="intel-notice-card">
                  <div className="intel-notice-icon">
                    <span className="material-symbols-outlined">troubleshoot</span>
                  </div>
                  <h3>Repository analysis required</h3>
                  <p>Run repository analysis to generate structural intelligence and CodeGraph IR 1.0.</p>
                  <button
                    type="button"
                    className="ws-btn ws-btn-primary"
                    onClick={() => setView("analysis")}
                  >
                    Analyze Repository
                  </button>
                </div>
              ) : (
                <>
                  {/* Real Graph IR Summary Metrics */}
                  <IntelligenceSummary graphData={activeGraph} loading={graphLoading} />

                  {/* Architecture Roles, Conceptual Layers & Pipeline */}
                  <ArchitectureOverview
                    graphData={activeGraph}
                    selectedRole={selectedRoleFilter}
                    onSelectRole={setSelectedRoleFilter}
                    selectedLayer={selectedLayerFilter}
                    onSelectLayer={setSelectedLayerFilter}
                  />

                  {/* Repository Tree & File Intelligence Inspector */}
                  <RepositoryTree
                    graphData={activeGraph}
                    selectedPath={selectedTreePath}
                    onSelectFile={setSelectedTreePath}
                  />

                  {/* Dependency Overview & Deterministic Architecture Health */}
                  <DependencyHealth graphData={activeGraph} />
                </>
              )}
            </div>
          )}

          {/* =========================================================
             INTERACTIVE CODEGRAPH WORKSPACE (PHASE 5)
             ========================================================= */}
          {view === "graph" && (
            <CodeGraphView
              graphData={activeGraph}
              activeRepo={selectedRepo}
              activeSnapshot={
                latestSelectedSnapshot
                  ? {
                      branch: latestSelectedSnapshot.branch || repoBranch,
                      commit_sha: latestSelectedSnapshot.commitSha,
                    }
                  : null
              }
              isLoading={graphLoading}
              error={graphError}
              onRetry={() => setRefreshCount((c) => c + 1)}
              setView={setView}
            />
          )}

          {/* API Map Placeholder */}
          {view === "apimap" && (
            <PlaceholderView
              title="API & Route Map"
              description="Coming next: Automatic HTTP endpoint discovery, controller mapping, and route-level code intelligence."
              icon="api"
              phase="Phase 5"
            />
          )}

          {/* Code Review Placeholder (Phase 8 Target) */}
          {view === "review" && (
            <PlaceholderView
              title="Code Review"
              description="Coming in Phase 8: Automated commit diff analysis, architectural impact assessment, affected components, and test suggestions."
              icon="rate_review"
              phase="Phase 8"
            />
          )}

          {/* Developer Learning Workspace */}
          {view === "learning" && (
            <section className="dashboard-content">
              <LearningView
                getToken={getToken}
                selectedRepo={selectedRepo}
                setView={setView}
              />
            </section>
          )}

          {/* Settings Placeholder (Phase 10 Target) */}
          {view === "settings" && (
            <PlaceholderView
              title="Settings"
              description="Coming in Phase 10: Workspace configuration, GitHub integration settings, AI provider parameters, and privacy controls."
              icon="settings"
              phase="Phase 10"
            />
          )}

          {/* Authenticated Profile */}
          {view === "profile" && (
            <section className="dashboard-content">
              <div className="profile-dashboard-card">
                <h2>Authenticated Profile</h2>

                {user ? (
                  <>
                    <div className="profile-row">
                      <span>Clerk User ID</span>
                      <code>{user.userId}</code>
                    </div>

                    <div className="profile-row">
                      <span>Status</span>
                      <strong>Authenticated</strong>
                    </div>
                  </>
                ) : (
                  <p>Loading profile...</p>
                )}
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}

export default Dashboard;
