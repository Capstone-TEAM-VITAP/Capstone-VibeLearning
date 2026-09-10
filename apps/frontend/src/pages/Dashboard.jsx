import { useEffect, useState } from "react";
import { useAuth, UserButton } from "@clerk/react";
import {
  getCurrentUser,
  listRepos,
  listSnapshots,
  getChangedFiles,
  getDiff,
} from "../services/api.js";
import AnalysisDemo from "../components/AnalysisDemo.jsx";
import ReposSection from "../components/ReposSection.jsx";

function Dashboard() {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const [user, setUser] = useState(null);
  const [repos, setRepos] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [view, setView] = useState("overview");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    async function loadDashboard() {
      try {
        setLoading(true);

        const userResponse = await getCurrentUser(getToken);
        setUser(userResponse.data);

        const repoData = await listRepos(getToken);
        setRepos(repoData);

        const allSnapshots = [];

        for (const repo of repoData) {
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
                console.warn(
                  "Could not load diff for snapshot:",
                  snapshot.commitSha,
                  error,
                );
              }

              allSnapshots.push({
                ...snapshot,

                repositoryName: `${repo.owner}/${repo.name}`,
                realFileCount: files?.fileCount || files?.files?.length || 0,

                realAdditions: diffData?.additions ?? snapshot.additions ?? 0,

                realDeletions: diffData?.deletions ?? snapshot.deletions ?? 0,
              });
            } catch (error) {
              console.warn(
                "Could not load changed files:",
                snapshot.commitSha,
                error,
              );

              allSnapshots.push({
                ...snapshot,
                repositoryName: `${repo.owner}/${repo.name}`,
                realFileCount: snapshot.fileCount || 0,
                realAdditions: snapshot.additions || 0,
                realDeletions: snapshot.deletions || 0,
              });
            }
          }
        }

        setSnapshots(allSnapshots);
      } catch (error) {
        console.error("Dashboard loading failed:", error);
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, [isLoaded, isSignedIn, getToken, view]);
  const totalFiles = snapshots.reduce(
    (sum, snapshot) => sum + (snapshot.realFileCount || 0),
    0,
  );

  const totalAdditions = snapshots.reduce(
    (sum, snapshot) => sum + (snapshot.realAdditions || 0),
    0,
  );

  const totalDeletions = snapshots.reduce(
    (sum, snapshot) => sum + (snapshot.realDeletions || 0),
    0,
  );

  const latestSnapshot = [...snapshots].sort(
    (a, b) => new Date(b.committedAt || 0) - new Date(a.committedAt || 0),
  )[0];

  function formatDate(date) {
    if (!date) return "—";

    return new Date(date).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }

  return (
    <div className="codeai-dashboard">
      {/* Sidebar */}
      <aside className="dashboard-sidebar">
        <div className="sidebar-brand">
          <h2>CodeAI</h2>
          <span>Developer Intelligence</span>
        </div>

        <nav className="dashboard-nav">
          <button
            className={view === "overview" ? "active" : ""}
            onClick={() => setView("overview")}
          >
            Overview
          </button>

          <button
            className={view === "repos" ? "active" : ""}
            onClick={() => setView("repos")}
          >
            Repositories
          </button>

          <button
            className={view === "analysis" ? "active" : ""}
            onClick={() => setView("analysis")}
          >
            Code Analysis
          </button>

          <button
            className={view === "profile" ? "active" : ""}
            onClick={() => setView("profile")}
          >
            Profile
          </button>
        </nav>
      </aside>

      {/* Main Dashboard */}
      <main className="dashboard-main">
        <header className="dashboard-topbar">
          <div>
            <h1>
              {view === "overview" && "Dashboard Overview"}
              {view === "repos" && "Repositories"}
              {view === "analysis" && "Code Analysis"}
              {view === "profile" && "Profile"}
            </h1>

            <p>
              {view === "overview" &&
                "Monitor your repositories and code intelligence."}
              {view === "repos" &&
                "Manage connected repositories and snapshots."}
              {view === "analysis" &&
                "Analyze your code changes and repository snapshots."}
              {view === "profile" && "Manage your CodeAI account information."}
            </p>
          </div>

          <UserButton />
        </header>

        {/* Overview */}
        {view === "overview" && (
          <section className="dashboard-content">
            {loading ? (
              <div className="dashboard-loading">Loading dashboard...</div>
            ) : (
              <>
                {/* Stats */}
                <div className="dashboard-stats">
                  <div className="stat-card">
                    <span>Repositories</span>
                    <strong>{repos.length}</strong>
                  </div>

                  <div className="stat-card">
                    <span>Snapshots</span>
                    <strong>{snapshots.length}</strong>
                  </div>

                  <div className="stat-card">
                    <span>Changed Files</span>
                    <strong>{totalFiles}</strong>
                  </div>

                  <div className="stat-card">
                    <span>Changes</span>
                    <strong>
                      +{totalAdditions} / -{totalDeletions}
                    </strong>
                  </div>
                </div>

                {/* Recent Activity */}
                <div className="dashboard-section">
                  <div className="section-heading">
                    <div>
                      <h2>Recent Activity</h2>
                      <p>Your latest repository snapshots.</p>
                    </div>
                  </div>

                  {snapshots.length === 0 ? (
                    <div className="empty-state">
                      <h3>No activity yet</h3>
                      <p>Connect a repository to start tracking your code.</p>

                      <button
                        className="dashboard-action"
                        onClick={() => setView("repos")}
                      >
                        Connect Repository
                      </button>
                    </div>
                  ) : (
                    <div className="activity-list">
                      {[...snapshots]
                        .sort(
                          (a, b) =>
                            new Date(b.committedAt || 0) -
                            new Date(a.committedAt || 0),
                        )
                        .slice(0, 5)
                        .map((snapshot) => (
                          <div
                            className="activity-item"
                            key={snapshot.id || snapshot.commitSha}
                          >
                            <div>
                              <strong>
                                {snapshot.message || "Repository snapshot"}
                              </strong>

                              <p>
                                {snapshot.commitSha?.slice(0, 8)} ·{" "}
                                {formatDate(snapshot.committedAt)}
                              </p>
                            </div>

                            <div className="activity-stats">
                              <span>{snapshot.realFileCount || 0} files</span>

                              <span className="addition">
                                +{snapshot.realAdditions || 0}
                              </span>

                              <span className="deletion">
                                -{snapshot.realDeletions || 0}
                              </span>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </div>

                {/* Repository Overview */}
                <div className="dashboard-section">
                  <div className="section-heading">
                    <div>
                      <h2>Connected Repositories</h2>
                      <p>Your repositories currently connected to CodeAI.</p>
                    </div>

                    <button
                      className="dashboard-action"
                      onClick={() => setView("repos")}
                    >
                      View Repositories
                    </button>
                  </div>

                  {repos.length === 0 ? (
                    <div className="empty-state">
                      <h3>No repositories connected</h3>
                      <p>
                        Connect your first GitHub repository to get started.
                      </p>
                    </div>
                  ) : (
                    <div className="repository-grid">
                      {repos.slice(0, 4).map((repo) => (
                        <div className="repository-card" key={repo.id}>
                          <div>
                            <h3>
                              {repo.owner}/{repo.name}
                            </h3>

                            <p>Branch: {repo.defaultBranch || "main"}</p>
                          </div>

                          <span className="repo-status">Connected</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Latest Snapshot */}
                {latestSnapshot && (
                  <div className="dashboard-section latest-snapshot">
                    <div className="section-heading">
                      <div>
                        <h2>Latest Snapshot</h2>
                        <p>Most recent commit captured by CodeAI.</p>
                      </div>
                    </div>

                    <div className="snapshot-overview">
                      <div>
                        <span>Commit</span>
                        <strong>{latestSnapshot.commitSha?.slice(0, 8)}</strong>
                      </div>

                      <div>
                        <span>Files</span>
                        <strong>{latestSnapshot.realFileCount || 0}</strong>
                      </div>

                      <div>
                        <span>Additions</span>
                        <strong className="addition">
                          <strong className="addition">
                            +{latestSnapshot.realAdditions || 0}
                          </strong>
                        </strong>
                      </div>

                      <div>
                        <span>Deletions</span>
                        <strong className="deletion">
                          -{latestSnapshot.realDeletions || 0}
                        </strong>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {/* Repositories */}
        {view === "repos" && (
          <section className="dashboard-content">
            <ReposSection getToken={getToken} />
          </section>
        )}

        {/* Analysis */}
        {view === "analysis" && (
          <section className="dashboard-content">
            <AnalysisDemo getToken={getToken} />
          </section>
        )}

        {/* Profile */}
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
  );
}

export default Dashboard;
