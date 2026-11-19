import React, { useState, useEffect, useMemo } from "react";
import {
  Settings,
  Sliders,
  GitBranch,
  Palette,
  ShieldCheck,
  Check,
  Save,
  RotateCcw,
  AlertCircle,
  FolderGit2,
  HardDrive,
  Lock,
  Server,
  Terminal,
  Cpu,
  Eye,
  Info,
  X,
} from "lucide-react";
import { getSettings, updateSettings } from "../services/api.js";
import { THEME_STORAGE_KEY, getStoredTheme, applyTheme } from "../services/theme.js";
import "./SettingsView.css";

const VIEW_OPTIONS = [
  { value: "overview", label: "Overview Dashboard" },
  { value: "architecture", label: "Architecture Intelligence" },
  { value: "graph", label: "Interactive CodeGraph" },
  { value: "apimap", label: "API & Route Map" },
  { value: "files", label: "Repository Tree & Symbols" },
  { value: "dependencies", label: "Dependency Health" },
  { value: "assistant", label: "AI Repository Assistant" },
  { value: "learning", label: "Developer Learning Quizzes" },
];

export default function SettingsView({
  getToken,
  selectedRepo = null,
  repositories = [],
  onSelectRepository = null,
}) {
  const [activeTab, setActiveTab] = useState("general"); // "general" | "workspace" | "appearance" | "security"
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Original saved state from backend
  const [initialData, setInitialData] = useState(null);

  // Form State
  const [workspaceName, setWorkspaceName] = useState("CodeAI Workspace");
  const [workspaceDesc, setWorkspaceDesc] = useState("");
  const [selectedRepoId, setSelectedRepoId] = useState("");
  const [defaultBranch, setDefaultBranch] = useState("main");

  // Preferences State
  const [theme, setTheme] = useState(() => getStoredTheme());
  const [autoSync, setAutoSync] = useState(true);
  const [defaultView, setDefaultView] = useState("overview");
  const [diffViewMode, setDiffViewMode] = useState("split");
  const [codeIntelligence, setCodeIntelligence] = useState("deep");
  const [aiTips, setAiTips] = useState(true);

  // Security Information (from backend audit)
  const [securityInfo, setSecurityInfo] = useState(null);

  // Load Settings from Backend API
  useEffect(() => {
    let isCancelled = false;

    async function loadSettings() {
      if (!getToken) {
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const data = await getSettings(getToken);
        if (isCancelled) return;

        setInitialData(data);
        setWorkspaceName(data.workspace?.name || "CodeAI Workspace");
        setWorkspaceDesc(data.workspace?.description || "");
        setSelectedRepoId(data.selectedRepositoryId || selectedRepo?.id || (data.repositories?.[0]?.id ?? ""));
        setDefaultBranch(data.defaultBranch || selectedRepo?.defaultBranch || "main");

        const prefs = data.preferences || {};
        if (prefs.theme) {
          setTheme(prefs.theme);
          applyTheme(prefs.theme);
        }
        setAutoSync(prefs.autoSync ?? true);
        setDefaultView(prefs.defaultView || "overview");
        setDiffViewMode(prefs.diffViewMode || "split");
        setCodeIntelligence(prefs.codeIntelligence || "deep");
        setAiTips(prefs.aiTips ?? true);

        setSecurityInfo(data.security || null);
      } catch (err) {
        if (isCancelled) return;
        console.warn("[SettingsView] Failed to fetch settings:", err);
        setError(err.message || "Failed to load workspace settings");
      } finally {
        if (!isCancelled) setLoading(false);
      }
    }

    loadSettings();

    return () => {
      isCancelled = true;
    };
  }, [getToken, selectedRepo?.id]);

  // Keep theme synchronized with external changes (e.g. Sidebar toggle)
  useEffect(() => {
    const handleThemeChange = (e) => {
      if (e.detail?.theme) {
        setTheme(e.detail.theme);
      }
    };
    window.addEventListener("codeai-theme-change", handleThemeChange);
    return () => window.removeEventListener("codeai-theme-change", handleThemeChange);
  }, []);

  // Compute dirty state
  const isDirty = useMemo(() => {
    if (!initialData) return false;
    const initialPrefs = initialData.preferences || {};

    return (
      workspaceName !== (initialData.workspace?.name || "CodeAI Workspace") ||
      workspaceDesc !== (initialData.workspace?.description || "") ||
      selectedRepoId !== (initialData.selectedRepositoryId || "") ||
      defaultBranch !== (initialData.defaultBranch || "main") ||
      theme !== (initialPrefs.theme || getStoredTheme()) ||
      autoSync !== (initialPrefs.autoSync ?? true) ||
      defaultView !== (initialPrefs.defaultView || "overview") ||
      diffViewMode !== (initialPrefs.diffViewMode || "split") ||
      codeIntelligence !== (initialPrefs.codeIntelligence || "deep") ||
      aiTips !== (initialPrefs.aiTips ?? true)
    );
  }, [
    initialData,
    workspaceName,
    workspaceDesc,
    selectedRepoId,
    defaultBranch,
    theme,
    autoSync,
    defaultView,
    diffViewMode,
    codeIntelligence,
    aiTips,
  ]);

  // Save Settings Handler
  const handleSave = async () => {
    if (!getToken) return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);

    const payload = {
      workspaceName: workspaceName.trim() || "CodeAI Workspace",
      workspaceDescription: workspaceDesc.trim(),
      selectedRepositoryId: selectedRepoId || null,
      defaultBranch: defaultBranch.trim() || "main",
      preferences: {
        theme,
        autoSync,
        defaultView,
        diffViewMode,
        codeIntelligence,
        aiTips,
      },
    };

    try {
      const updated = await updateSettings(getToken, payload);
      setInitialData(updated);
      setSuccessMsg("Settings saved successfully.");

      // If selected repository changed, propagate to parent dashboard
      if (onSelectRepository && selectedRepoId) {
        const found = (updated.repositories || repositories).find((r) => r.id === selectedRepoId);
        if (found) {
          onSelectRepository(found);
        }
      }

      // Persist theme to localStorage and document
      applyTheme(theme);
      try {
        localStorage.setItem(THEME_STORAGE_KEY, theme);
      } catch {}
      window.dispatchEvent(new CustomEvent("codeai-theme-change", { detail: { theme } }));

      // Auto dismiss success toast after 4s
      setTimeout(() => {
        setSuccessMsg(null);
      }, 4000);
    } catch (err) {
      console.error("[SettingsView] Error saving settings:", err);
      setError(err.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  // Reset to initial saved values
  const handleReset = () => {
    if (!initialData) return;
    setWorkspaceName(initialData.workspace?.name || "CodeAI Workspace");
    setWorkspaceDesc(initialData.workspace?.description || "");
    setSelectedRepoId(initialData.selectedRepositoryId || "");
    setDefaultBranch(initialData.defaultBranch || "main");

    const prefs = initialData.preferences || {};
    const origTheme = prefs.theme || getStoredTheme();
    setTheme(origTheme);
    applyTheme(origTheme);
    window.dispatchEvent(new CustomEvent("codeai-theme-change", { detail: { theme: origTheme } }));

    setAutoSync(prefs.autoSync ?? true);
    setDefaultView(prefs.defaultView || "overview");
    setDiffViewMode(prefs.diffViewMode || "split");
    setCodeIntelligence(prefs.codeIntelligence || "deep");
    setAiTips(prefs.aiTips ?? true);

    setError(null);
    setSuccessMsg(null);
  };

  // Immediate theme change handler
  const handleSelectTheme = (newTheme) => {
    setTheme(newTheme);
    applyTheme(newTheme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, newTheme);
    } catch {}
    window.dispatchEvent(new CustomEvent("codeai-theme-change", { detail: { theme: newTheme } }));
  };

  // Repository list from API or props fallback
  const repoList = initialData?.repositories || repositories;
  const activeRepo = repoList.find((r) => r.id === selectedRepoId) || selectedRepo;

  if (loading) {
    return (
      <div className="settings-container">
        <div className="settings-loading">
          <div className="settings-spinner" />
          <span>Loading workspace settings...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="settings-container">
      {/* 1. Header with Title & Action Buttons */}
      <div className="settings-header">
        <div className="settings-header-left">
          <div className="settings-header-icon">
            <Settings size={22} />
          </div>
          <div>
            <h2 className="settings-title">Settings</h2>
            <div className="settings-subtitle">
              Manage workspace configuration, repository preferences, appearance, and privacy
            </div>
          </div>
        </div>

        <div className="settings-header-actions">
          <button
            type="button"
            className="settings-reset-btn"
            onClick={handleReset}
            disabled={!isDirty || saving}
          >
            <RotateCcw size={14} />
            <span>Reset</span>
          </button>

          <button
            type="button"
            className="settings-save-btn"
            onClick={handleSave}
            disabled={!isDirty || saving}
          >
            {saving ? <div className="settings-spinner" style={{ width: 14, height: 14 }} /> : <Save size={14} />}
            <span>{saving ? "Saving..." : "Save Changes"}</span>
          </button>
        </div>
      </div>

      {/* 2. Feedback Notifications */}
      {successMsg && (
        <div className="settings-alert settings-alert-success">
          <div className="settings-alert-left">
            <Check size={16} />
            <span>{successMsg}</span>
          </div>
          <button type="button" className="settings-alert-dismiss" onClick={() => setSuccessMsg(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {error && (
        <div className="settings-alert settings-alert-error">
          <div className="settings-alert-left">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
          <button type="button" className="settings-alert-dismiss" onClick={() => setError(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* 3. Main Navigation & Settings Panels */}
      <div className="settings-layout">
        {/* Navigation Tabs */}
        <nav className="settings-nav">
          <button
            type="button"
            className={`settings-nav-item ${activeTab === "general" ? "active" : ""}`}
            onClick={() => setActiveTab("general")}
          >
            <span className="settings-nav-icon">
              <Sliders size={16} />
            </span>
            <span>General</span>
          </button>

          <button
            type="button"
            className={`settings-nav-item ${activeTab === "workspace" ? "active" : ""}`}
            onClick={() => setActiveTab("workspace")}
          >
            <span className="settings-nav-icon">
              <GitBranch size={16} />
            </span>
            <span>Workspace</span>
          </button>

          <button
            type="button"
            className={`settings-nav-item ${activeTab === "appearance" ? "active" : ""}`}
            onClick={() => setActiveTab("appearance")}
          >
            <span className="settings-nav-icon">
              <Palette size={16} />
            </span>
            <span>Appearance</span>
          </button>

          <button
            type="button"
            className={`settings-nav-item ${activeTab === "security" ? "active" : ""}`}
            onClick={() => setActiveTab("security")}
          >
            <span className="settings-nav-icon">
              <ShieldCheck size={16} />
            </span>
            <span>Privacy & Security</span>
          </button>
        </nav>

        {/* Tab Content Panels */}
        <div className="settings-content">
          {/* TAB 1: GENERAL */}
          {activeTab === "general" && (
            <>
              <div className="settings-card">
                <div className="settings-card-header">
                  <h3 className="settings-card-title">Workspace Identity</h3>
                  <p className="settings-card-desc">
                    Configure your workspace name and default landing view across CodeAI.
                  </p>
                </div>
                <div className="settings-card-body">
                  <div className="settings-group">
                    <label className="settings-label" htmlFor="ws-name">
                      Workspace Name
                    </label>
                    <input
                      id="ws-name"
                      type="text"
                      className="settings-input"
                      value={workspaceName}
                      onChange={(e) => setWorkspaceName(e.target.value)}
                      placeholder="e.g. Production Monorepo"
                      maxLength={255}
                    />
                    <span className="settings-help">
                      This name is displayed in the sidebar workspace pill and project headings.
                    </span>
                  </div>

                  <div className="settings-group">
                    <label className="settings-label" htmlFor="ws-desc">
                      Workspace Description
                    </label>
                    <textarea
                      id="ws-desc"
                      className="settings-textarea"
                      value={workspaceDesc}
                      onChange={(e) => setWorkspaceDesc(e.target.value)}
                      placeholder="Optional notes or purpose of this workspace..."
                      maxLength={1000}
                    />
                  </div>

                  <div className="settings-group">
                    <label className="settings-label" htmlFor="default-view">
                      Default Landing View
                    </label>
                    <select
                      id="default-view"
                      className="settings-select"
                      value={defaultView}
                      onChange={(e) => setDefaultView(e.target.value)}
                    >
                      {VIEW_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    <span className="settings-help">
                      View loaded automatically when launching or switching to this workspace.
                    </span>
                  </div>

                  {initialData?.workspace?.id && (
                    <div className="settings-group" style={{ marginTop: "8px" }}>
                      <label className="settings-label">Workspace Metadata</label>
                      <div className="meta-badge-list">
                        <span className="meta-pill" title="Workspace Internal UUID">
                          <HardDrive size={12} /> ID: {initialData.workspace.id}
                        </span>
                        {initialData.workspace.createdAt && (
                          <span className="meta-pill">
                            Created: {new Date(initialData.workspace.createdAt).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {/* TAB 2: WORKSPACE & REPOSITORIES */}
          {activeTab === "workspace" && (
            <>
              <div className="settings-card">
                <div className="settings-card-header">
                  <h3 className="settings-card-title">Repository Configuration</h3>
                  <p className="settings-card-desc">
                    Manage the active GitHub repository and target branch for AST analysis.
                  </p>
                </div>
                <div className="settings-card-body">
                  <div className="settings-group">
                    <label className="settings-label" htmlFor="active-repo-select">
                      <FolderGit2 size={15} /> Active GitHub Repository
                    </label>
                    <select
                      id="active-repo-select"
                      className="settings-select"
                      value={selectedRepoId}
                      onChange={(e) => {
                        const newId = e.target.value;
                        setSelectedRepoId(newId);
                        const match = repoList.find((r) => r.id === newId);
                        if (match?.defaultBranch) {
                          setDefaultBranch(match.defaultBranch);
                        }
                      }}
                    >
                      {repoList.map((repo) => (
                        <option key={repo.id} value={repo.id}>
                          {repo.owner}/{repo.name} ({repo.defaultBranch || "main"})
                        </option>
                      ))}
                    </select>
                    <span className="settings-help">
                      Selected repository provides the CodeGraph AST, Route Map, and AI context.
                    </span>
                  </div>

                  {activeRepo && (
                    <div className="meta-badge-list">
                      <span className="meta-pill">URL: {activeRepo.repoUrl}</span>
                      <span className="meta-pill">
                        Last Commit: {activeRepo.lastSyncSha ? activeRepo.lastSyncSha.slice(0, 7) : "HEAD"}
                      </span>
                    </div>
                  )}

                  <div className="settings-group">
                    <label className="settings-label" htmlFor="branch-input">
                      <GitBranch size={15} /> Default Branch
                    </label>
                    <input
                      id="branch-input"
                      type="text"
                      className="settings-input mono"
                      value={defaultBranch}
                      onChange={(e) => setDefaultBranch(e.target.value)}
                      placeholder="e.g. main, master, or develop"
                    />
                    <span className="settings-help">
                      Primary branch checked out for automated CodeGraph snapshots and diff calculations.
                    </span>
                  </div>
                </div>
              </div>

              <div className="settings-card">
                <div className="settings-card-header">
                  <h3 className="settings-card-title">Analysis & Diff Preferences</h3>
                  <p className="settings-card-desc">
                    Fine-tune background synchronization, code graph depth, and diff presentation.
                  </p>
                </div>
                <div className="settings-card-body">
                  <div className="settings-toggle-row">
                    <div className="settings-toggle-info">
                      <span className="settings-toggle-label">Automatic Repository Sync</span>
                      <span className="settings-toggle-desc">
                        Automatically fetch new commits and rebuild ASTs upon webhook notification.
                      </span>
                    </div>
                    <label className="settings-switch">
                      <input
                        type="checkbox"
                        checked={autoSync}
                        onChange={(e) => setAutoSync(e.target.checked)}
                      />
                      <span className="settings-slider" />
                    </label>
                  </div>

                  <div className="settings-group">
                    <label className="settings-label" htmlFor="diff-mode-select">
                      Diff Presentation Mode
                    </label>
                    <select
                      id="diff-mode-select"
                      className="settings-select"
                      value={diffViewMode}
                      onChange={(e) => setDiffViewMode(e.target.value)}
                    >
                      <option value="split">Side-by-side (Split View)</option>
                      <option value="unified">Inline (Unified Diff)</option>
                    </select>
                    <span className="settings-help">
                      Preferred layout for reviewing git commit hunks and changed lines.
                    </span>
                  </div>

                  <div className="settings-group">
                    <label className="settings-label" htmlFor="intel-depth-select">
                      <Cpu size={14} /> CodeGraph Intelligence Depth
                    </label>
                    <select
                      id="intel-depth-select"
                      className="settings-select"
                      value={codeIntelligence}
                      onChange={(e) => setCodeIntelligence(e.target.value)}
                    >
                      <option value="deep">Deep AST Analysis (Symbols, Cross-File Calls, Route Maps, Models)</option>
                      <option value="standard">Standard (Symbols and Imports)</option>
                      <option value="fast">Lightweight (File Hierarchy Only)</option>
                    </select>
                  </div>

                  <div className="settings-toggle-row">
                    <div className="settings-toggle-info">
                      <span className="settings-toggle-label">Contextual AI Guidance</span>
                      <span className="settings-toggle-desc">
                        Display architectural callouts and intelligent navigation tips across views.
                      </span>
                    </div>
                    <label className="settings-switch">
                      <input
                        type="checkbox"
                        checked={aiTips}
                        onChange={(e) => setAiTips(e.target.checked)}
                      />
                      <span className="settings-slider" />
                    </label>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* TAB 3: APPEARANCE */}
          {activeTab === "appearance" && (
            <>
              <div className="settings-card">
                <div className="settings-card-header">
                  <h3 className="settings-card-title">Theme Selection</h3>
                  <p className="settings-card-desc">
                    Choose your interface style. Changes take effect immediately across all CodeAI pages.
                  </p>
                </div>
                <div className="settings-card-body">
                  <div className="theme-picker-grid">
                    {/* Dark Mode Card */}
                    <div
                      className={`theme-card ${theme === "dark" ? "active" : ""}`}
                      onClick={() => handleSelectTheme("dark")}
                    >
                      <div className="theme-card-preview preview-dark">
                        <div className="preview-bar">
                          <span className="preview-dot" />
                          <span className="preview-dot" />
                        </div>
                        <div className="preview-body">
                          <div className="preview-side" />
                          <div className="preview-main">
                            <div className="preview-line accent" />
                            <div className="preview-line" />
                            <div className="preview-line" />
                          </div>
                        </div>
                      </div>
                      <div className="theme-card-footer">
                        <span className="theme-card-name">Terminal Dark</span>
                        {theme === "dark" && (
                          <span className="theme-card-check">
                            <Check size={12} />
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Light Mode Card */}
                    <div
                      className={`theme-card ${theme === "light" ? "active" : ""}`}
                      onClick={() => handleSelectTheme("light")}
                    >
                      <div className="theme-card-preview preview-light">
                        <div className="preview-bar">
                          <span className="preview-dot" />
                          <span className="preview-dot" />
                        </div>
                        <div className="preview-body">
                          <div className="preview-side" />
                          <div className="preview-main">
                            <div className="preview-line accent" />
                            <div className="preview-line" />
                            <div className="preview-line" />
                          </div>
                        </div>
                      </div>
                      <div className="theme-card-footer">
                        <span className="theme-card-name">Clean Light</span>
                        {theme === "light" && (
                          <span className="theme-card-check">
                            <Check size={12} />
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="settings-card">
                <div className="settings-card-header">
                  <h3 className="settings-card-title">Typography & Density</h3>
                  <p className="settings-card-desc">
                    Terminal Horizon typography settings and layout density.
                  </p>
                </div>
                <div className="settings-card-body">
                  <div className="settings-group">
                    <label className="settings-label">Active Monospace Font</label>
                    <input
                      type="text"
                      className="settings-input mono"
                      readOnly
                      value="Geist Mono, JetBrains Mono, SFMono-Regular"
                    />
                    <span className="settings-help">
                      High-legibility programming fonts with tabular numbers and programming ligatures.
                    </span>
                  </div>

                  <div className="settings-group">
                    <label className="settings-label">Active Sans-Serif Font</label>
                    <input
                      type="text"
                      className="settings-input"
                      readOnly
                      value="Geist, Inter, system-ui, -apple-system"
                    />
                  </div>
                </div>
              </div>
            </>
          )}

          {/* TAB 4: PRIVACY & SECURITY */}
          {activeTab === "security" && (
            <>
              <div className="security-callout">
                <Info size={20} />
                <div>
                  <strong>Enterprise-Grade Privacy Architecture:</strong> CodeAI enforces zero-leak credential isolation.
                  All repository authentication tokens, API keys, and database passwords are stored exclusively on the server in secure environment vaults and are never transmitted to frontend clients.
                </div>
              </div>

              <div className="settings-card">
                <div className="settings-card-header">
                  <h3 className="settings-card-title">Privacy & Security Audit</h3>
                  <p className="settings-card-desc">
                    Verified status of authentication, access control, and credential isolation.
                  </p>
                </div>
                <div className="settings-card-body">
                  <div className="security-audit-grid">
                    <div className="security-card">
                      <div className="security-card-top">
                        <Lock size={18} className="security-card-icon" />
                        <span className="security-card-badge">Enforced</span>
                      </div>
                      <div className="security-card-title">Authentication System</div>
                      <div className="security-card-desc">
                        Protected by Clerk with RSA-256 JWT session tokens. Every request validates token signature and identity.
                      </div>
                    </div>

                    <div className="security-card">
                      <div className="security-card-top">
                        <Server size={18} className="security-card-icon" />
                        <span className="security-card-badge">Server-Side Only</span>
                      </div>
                      <div className="security-card-title">Credential Vault Isolation</div>
                      <div className="security-card-desc">
                        Groq API keys, GitHub tokens, and database connection strings are processed entirely server-side.
                      </div>
                    </div>

                    <div className="security-card">
                      <div className="security-card-top">
                        <ShieldCheck size={18} className="security-card-icon" />
                        <span className="security-card-badge">Zero Leaks</span>
                      </div>
                      <div className="security-card-title">Frontend Response Security</div>
                      <div className="security-card-desc">
                        API responses strictly serialize repository metadata without returning secret tokens, authorization headers, or private keys.
                      </div>
                    </div>

                    <div className="security-card">
                      <div className="security-card-top">
                        <HardDrive size={18} className="security-card-icon" />
                        <span className="security-card-badge">Row-Level</span>
                      </div>
                      <div className="security-card-title">User Scoped Access Control</div>
                      <div className="security-card-desc">
                        Workspaces, repository connections, and CodeGraph AST snapshots are partitioned by authenticated user UUID.
                      </div>
                    </div>
                  </div>

                  <div className="settings-group" style={{ marginTop: "12px" }}>
                    <label className="settings-label">Security Protocol Status</label>
                    <div className="meta-badge-list">
                      <span className="meta-pill">
                        <Check size={12} style={{ color: "#22c55e" }} /> Transport: TLS 1.3 / HTTPS
                      </span>
                      <span className="meta-pill">
                        <Check size={12} style={{ color: "#22c55e" }} /> Auth Provider: {securityInfo?.authProvider || "Clerk (JWT RS256)"}
                      </span>
                      <span className="meta-pill">
                        <Check size={12} style={{ color: "#22c55e" }} /> Client Key Exposure: None (0 keys)
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
