import { useEffect, useState } from "react";
import { useAuth } from "@clerk/react";
import {
  CircleDot,
  CircleX,
  Clock,
  FolderOpen,
  FolderX,
  GitCompare,
  GitFork,
  GitPullRequest,
  Plus,
  RefreshCw,
  Settings,
  MessageSquareText,
  Terminal,
  Webhook,
  Workflow,
  Wrench,
} from "lucide-react";
import {
  getCurrentUser,
  listRepos,
  listSnapshots,
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
import IntelligenceCharts from "../components/IntelligenceCharts.jsx";
import AiSummaryPanel from "../components/AiSummaryPanel.jsx";
import DependencyHealth from "../components/DependencyHealth.jsx";
import CodeGraphView from "../components/CodeGraphView.jsx";
import ApiMapView from "../components/ApiMapView.jsx";
import LearningView from "../components/LearningView.jsx";
import SettingsView from "../components/SettingsView.jsx";
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

const PLACEHOLDER_ICONS = {
  api: Webhook,
  rate_review: GitPullRequest,
  settings: Settings,
};

function PlaceholderView({ title, description, icon, phase }) {
  const Icon = PLACEHOLDER_ICONS[icon] ?? Settings;
  return (
    <div className="workstation-placeholder">
      <div className="placeholder-icon-box">
        <Icon size={26} />
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
      <div className="placeholder-meta">
        <span className="placeholder-badge">
          <Clock size={14} />
          Coming in {phase}
        </span>
        <span className="placeholder-badge">
          <Terminal size={14} />
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

            // The backend stores per-snapshot totals (and fills in rows
            // saved before it did), so no per-snapshot diff calls here.
            for (const snapshot of repoSnapshots) {
              allSnapshots.push({
                ...snapshot,
                repositoryId: repo.id,
                repositoryName: `${repo.owner}/${repo.name}`,
                realFileCount: snapshot.fileCount || 0,
                realAdditions: snapshot.additions || 0,
                realDeletions: snapshot.deletions || 0,
              });
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

  // Change since the previous snapshot (only files are known per snapshot)
  const previousSelectedSnapshot = [...selectedRepoSnapshots].sort(
    (a, b) => new Date(b.committedAt || 0) - new Date(a.committedAt || 0),
  )[1];
  const metricDeltas = {
    parsedFiles:
      latestSelectedSnapshot?.realFileCount != null &&
      previousSelectedSnapshot?.realFileCount != null
        ? latestSelectedSnapshot.realFileCount - previousSelectedSnapshot.realFileCount
        : null,
  };

  // Newest-first activity feed across all connected repositories
  const repoNameById = Object.fromEntries(
    repos.map((r) => [r.id, r.owner ? `${r.owner}/${r.name}` : r.name]),
  );
  const activityItems = [...snapshots]
    .sort((a, b) => new Date(b.committedAt || 0) - new Date(a.committedAt || 0))
    .map((snap) => ({
      ...snap,
      repositoryName: snap.repositoryName || repoNameById[snap.repositoryId],
    }));

  // Single-key shortcuts on the overview (shown as hints next to actions)
  useEffect(() => {
    if (view !== "overview") return undefined;
    const keyMap = { n: "repos", r: "analysis", g: "graph", a: "assistant", i: "intelligence" };
    function onKey(e) {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
      const t = e.target;
      if (t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName))) return;
      const target = keyMap[e.key.toLowerCase()];
      if (target) {
        e.preventDefault();
        setView(target);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view]);

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

  // Each Repository Intelligence sub-page has its own title and focus
  const INTEL_PAGES = {
    intelligence: {
      title: "Repository Intelligence",
      desc: "AI summary and the key numbers from this repository's code graph.",
    },
    architecture: {
      title: "Architecture",
      desc: "How files are classified into roles and layers, and how those layers depend on each other.",
    },
    files: {
      title: "Files",
      desc: "Browse the repository tree and inspect any file's role, symbols and relationships.",
    },
    dependencies: {
      title: "Dependencies",
      desc: "External packages, the most depended-on files, and dependency health checks.",
    },
  };
  const intelPage = INTEL_PAGES[view] || INTEL_PAGES.intelligence;

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
      <div className={`codeai-main-container ${view === "graph" ? "codeai-main-container--graph" : view === "assistant" ? "codeai-main-container--assistant" : ""}`}>
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
        <main className={`codeai-page-content ${view === "graph" ? "codeai-page-content--fullbleed" : view === "assistant" ? "codeai-page-content--assistant" : ""}`}>
          {/* =========================================================
             OVERVIEW DASHBOARD (PHASE 3)
             ========================================================= */}
          {view === "overview" && (
            <div className="overview-container">
              {/* Title row */}
              <div className="overview-hero">
                <div className="overview-hero-text">
                  <h1 className="overview-title">Overview</h1>
                  <p className="overview-subtitle">
                    Understand, review and learn unfamiliar code.
                  </p>
                </div>
                <div className="overview-hero-actions">
                  <button
                    type="button"
                    className="ws-btn ws-btn-secondary"
                    onClick={() => setView("assistant")}
                  >
                    <MessageSquareText size={14} />
                    Ask AI
                    <kbd className="ws-kbd">A</kbd>
                  </button>
                  <button
                    type="button"
                    className="ws-btn ws-btn-primary"
                    onClick={() => setView("repos")}
                  >
                    <Plus size={14} />
                    Connect repository
                  </button>
                </div>
              </div>

              {/* Metric bar */}
              <MetricStrip
                metrics={intelligenceMetrics}
                deltas={metricDeltas}
                lastSnapshotAt={latestSelectedSnapshot?.committedAt || null}
                loading={loading}
              />

              {/* Primary repository */}
              {selectedRepo && (
                <RepositoryOverviewCard
                  repo={selectedRepo}
                  status={analysisStatus || "Not analyzed"}
                  roles={detectedRoles}
                  graphData={activeGraph}
                  onExploreIntelligence={() => setView("intelligence")}
                  onExploreGraph={() => setView("graph")}
                />
              )}

              <div className="overview-grid">
                {/* Connected repositories */}
                <section className="console-card">
                  <div className="console-card-head">
                    <h2 className="console-card-title">
                      Connected repositories <small>{repos.length}</small>
                    </h2>
                    {repos.length > 0 && (
                      <button
                        type="button"
                        className="ws-btn ws-btn-ghost"
                        onClick={() => setView("repos")}
                      >
                        Manage all
                      </button>
                    )}
                  </div>

                  {repos.length === 0 ? (
                    <div className="overview-empty-repo">
                      <FolderOpen size={20} />
                      <h3>No repositories connected</h3>
                      <p>Connect a GitHub repository to build its code graph.</p>
                      <button
                        type="button"
                        className="ws-btn ws-btn-primary"
                        onClick={() => setView("repos")}
                      >
                        <Plus size={14} />
                        Connect repository
                      </button>
                    </div>
                  ) : (
                    <div className="console-table-wrap">
                      <table className="console-table">
                        <thead>
                          <tr>
                            <th>Repository</th>
                            <th>Branch</th>
                            <th>Status</th>
                            <th>Snapshot</th>
                            <th aria-label="Actions" />
                          </tr>
                        </thead>
                        <tbody>
                          {repos.map((repo) => {
                            const isSelected = repo.id === selectedRepo?.id;
                            const repoSnaps = snapshots.filter(
                              (snap) => snap.repositoryId === repo.id,
                            );
                            const latestSnap = [...repoSnaps].sort(
                              (a, b) =>
                                new Date(b.committedAt || 0) -
                                new Date(a.committedAt || 0),
                            )[0];
                            const isAnalyzed = repoSnaps.length > 0;
                            const isSyncing = syncingId === repo.id;

                            return (
                              <tr key={repo.id} className={isSelected ? "selected" : ""}>
                                <td>
                                  <button
                                    type="button"
                                    className="console-link"
                                    onClick={() => handleSelectRepository(repo)}
                                    title="Make this the active repository"
                                  >
                                    {repo.owner}/{repo.name}
                                  </button>
                                </td>
                                <td className="mono">{repo.defaultBranch || "main"}</td>
                                <td>
                                  <span className="console-status">
                                    <span className={`console-dot ${isAnalyzed ? "ok" : ""}`} />
                                    {isAnalyzed ? "Analyzed" : "Not analyzed"}
                                  </span>
                                </td>
                                <td className="mono">
                                  {latestSnap?.commitSha ? latestSnap.commitSha.slice(0, 7) : "—"}
                                </td>
                                <td>
                                  <div className="console-row-actions">
                                    <button
                                      type="button"
                                      className="ws-btn ws-btn-secondary"
                                      onClick={() => {
                                        handleSelectRepository(repo);
                                        setView(isAnalyzed ? "repos" : "analysis");
                                      }}
                                    >
                                      {isAnalyzed ? "Open" : "Analyze"}
                                    </button>
                                    <button
                                      type="button"
                                      className="ws-btn ws-btn-ghost"
                                      onClick={() => handleSyncRepo(repo.id)}
                                      disabled={isSyncing}
                                      aria-label={isSyncing ? "Syncing" : "Sync repository"}
                                      title="Sync from GitHub"
                                    >
                                      <RefreshCw
                                        size={14}
                                        style={{
                                          animation: isSyncing ? "spin 1s linear infinite" : "none",
                                        }}
                                      />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                {/* Recent activity */}
                <RecentActivity
                  activities={activityItems}
                  onViewAll={() => setView("repos")}
                />
              </div>

              {/* Quick actions */}
              <section className="console-card">
                <div className="console-card-head">
                  <h2 className="console-card-title">Quick actions</h2>
                </div>
                <ul className="quick-cmds">
                  <li>
                    <button type="button" onClick={() => setView("repos")}>
                      <Plus size={15} />
                      Connect repository
                      <kbd className="ws-kbd">N</kbd>
                    </button>
                  </li>
                  <li>
                    <button type="button" onClick={() => setView("analysis")}>
                      <Wrench size={15} />
                      Analyze snapshot
                      <kbd className="ws-kbd">R</kbd>
                    </button>
                  </li>
                  <li>
                    <button type="button" onClick={() => setView("graph")}>
                      <Workflow size={15} />
                      Explore CodeGraph
                      <kbd className="ws-kbd">G</kbd>
                    </button>
                  </li>
                  <li>
                    <button type="button" onClick={() => setView("assistant")}>
                      <MessageSquareText size={15} />
                      Ask AI
                      <kbd className="ws-kbd">A</kbd>
                    </button>
                  </li>
                  <li>
                    <button type="button" onClick={() => setView("review")}>
                      <GitPullRequest size={15} />
                      Code review
                      <span className="quick-cmds-soon">soon</span>
                    </button>
                  </li>
                </ul>
              </section>
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
            <section className="dashboard-content dashboard-content--assistant">
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
                      <Terminal size={14} />
                      Repository Intelligence
                    </span>
                    <h1 className="intel-hero-title">{intelPage.title}</h1>
                    <p className="intel-hero-desc">{intelPage.desc}</p>
                  </div>

                  <div className="intel-hero-actions">
                    <button
                      type="button"
                      className="ws-btn ws-btn-secondary"
                      onClick={() => setView("analysis")}
                    >
                      <MessageSquareText size={16} />
                      Ask AI
                    </button>

                    <button
                      type="button"
                      className="ws-btn ws-btn-secondary"
                      onClick={() => setView("graph")}
                    >
                      <Workflow size={16} />
                      Explore CodeGraph
                    </button>

                    <button
                      type="button"
                      className="ws-btn ws-btn-secondary"
                      onClick={() => setView("repos")}
                    >
                      <GitCompare size={16} />
                      Analyze Changes
                    </button>
                  </div>
                </div>

                {/* Repository Context Cluster */}
                <div className="intel-meta-cluster">
                  <div className="intel-meta-tag">
                    <FolderOpen size={13} />
                    <span>Repository: <strong>{selectedRepo ? `${selectedRepo.owner}/${selectedRepo.name}` : "—"}</strong></span>
                  </div>

                  <div className="intel-meta-tag">
                    <GitFork size={13} />
                    <span>Branch: <strong>{repoBranch || "—"}</strong></span>
                  </div>

                  <div className="intel-meta-tag">
                    <CircleDot size={13} />
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
                    <FolderX size={24} />
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
                    <RefreshCw
                      size={24}
                      style={{ animation: "spin 1.2s linear infinite" }}
                    />
                  </div>
                  <h3>Loading repository intelligence...</h3>
                  <p>Fetching canonical Graph IR 1.0 AST nodes and relationships.</p>
                </div>
              ) : graphError ? (
                <div className="intel-notice-card">
                  <div className="intel-notice-icon" style={{ color: "var(--status-error)" }}>
                    <CircleX size={24} />
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
                    <Wrench size={24} />
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
                  {view === "intelligence" && (
                    <>
                      {/* AI briefing for this commit (DeepSeek via OpenCode Go by default) */}
                      <AiSummaryPanel
                        getToken={getToken}
                        repoId={selectedRepo.id}
                        commitSha={latestSelectedSnapshot?.commitSha || null}
                      />
                      {/* Concrete counts from the graph as ranked bar charts */}
                      <IntelligenceCharts graphData={activeGraph} />
                    </>
                  )}

                  {view === "architecture" && (
                    <>
                      <IntelligenceCharts graphData={activeGraph} charts={["roles", "directories"]} />
                      <ArchitectureOverview
                        graphData={activeGraph}
                        selectedRole={selectedRoleFilter}
                        onSelectRole={setSelectedRoleFilter}
                        selectedLayer={selectedLayerFilter}
                        onSelectLayer={setSelectedLayerFilter}
                      />
                    </>
                  )}

                  {view === "files" && (
                    <>
                      <IntelligenceCharts graphData={activeGraph} charts={["languages", "symbolsPerFile"]} />
                      <RepositoryTree
                        graphData={activeGraph}
                        selectedPath={selectedTreePath}
                        onSelectFile={setSelectedTreePath}
                      />
                    </>
                  )}

                  {view === "dependencies" && (
                    <>
                      <IntelligenceCharts graphData={activeGraph} charts={["packages", "mostImported"]} />
                      <DependencyHealth graphData={activeGraph} />
                    </>
                  )}
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

          {/* API & Route Map View */}
          {view === "apimap" && (
            <ApiMapView
              repository={selectedRepo}
              snapshot={latestSelectedSnapshot}
              graphData={graphData}
              getToken={getToken}
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

          {/* Settings View */}
          {view === "settings" && (
            <SettingsView
              getToken={getToken}
              selectedRepo={selectedRepo}
              repositories={repos}
              onSelectRepository={handleSelectRepository}
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
