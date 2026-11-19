import { projectRepository } from "../repositories/project.repository.js";
import { repositoryRepository } from "../repositories/repository.repository.js";
import { userRepository } from "../repositories/user.repository.js";
import { UnauthorizedError } from "../utils/errors.js";

export const DEFAULT_PREFERENCES = {
  theme: "dark",
  autoSync: true,
  defaultView: "overview",
  diffViewMode: "split",
  codeIntelligence: "deep",
  aiTips: true,
  telemetry: false,
};

export const settingsService = {
  async _resolveUser(clerkUserId) {
    if (!clerkUserId) {
      throw new UnauthorizedError("Authentication required");
    }
    return userRepository.findOrCreateByClerkId(clerkUserId);
  },

  async _getOrCreateDefaultWorkspace(user) {
    const projects = await projectRepository.findManyByUserId(user.id);
    if (projects.length > 0) {
      return projects[0];
    }
    // Automatically initialize default workspace for user
    const defaultProject = await projectRepository.create({
      name: "CodeAI Workspace",
      description: JSON.stringify(DEFAULT_PREFERENCES),
      userId: user.id,
    });
    return defaultProject;
  },

  _parsePreferences(description) {
    if (!description) return { ...DEFAULT_PREFERENCES };
    try {
      const parsed = JSON.parse(description);
      if (typeof parsed === "object" && parsed !== null) {
        const prefs = parsed.preferences || parsed;
        return {
          ...DEFAULT_PREFERENCES,
          ...prefs,
        };
      }
    } catch {
      // not JSON formatted description, preserve defaults
    }
    return { ...DEFAULT_PREFERENCES };
  },

  /**
   * Return workspace settings, connected repositories, preferences, and privacy information.
   * Strictly scoped to the authenticated Clerk user. Never exposes sensitive secrets.
   */
  async getSettings(clerkUserId) {
    const user = await this._resolveUser(clerkUserId);
    const workspace = await this._getOrCreateDefaultWorkspace(user);
    const repos = await repositoryRepository.findManyByUserId(user.id);

    const preferences = this._parsePreferences(workspace.description);

    let selectedRepo = null;
    if (preferences.selectedRepositoryId) {
      selectedRepo = repos.find((r) => r.id === preferences.selectedRepositoryId);
    }
    if (!selectedRepo && repos.length > 0) {
      selectedRepo = repos[0];
    }

    const defaultBranch = selectedRepo?.defaultBranch || preferences.defaultBranch || "main";

    // Clean description if it was used for storing preferences JSON
    const displayDescription =
      workspace.description && workspace.description.trim().startsWith("{")
        ? ""
        : workspace.description || "";

    return {
      workspace: {
        id: workspace.id,
        name: workspace.name,
        description: displayDescription,
        createdAt: workspace.createdAt,
        updatedAt: workspace.updatedAt,
      },
      selectedRepositoryId: selectedRepo?.id || null,
      selectedRepository: selectedRepo
        ? {
            id: selectedRepo.id,
            name: selectedRepo.name,
            owner: selectedRepo.owner,
            defaultBranch: selectedRepo.defaultBranch,
            repoUrl: selectedRepo.repoUrl,
            lastSyncSha: selectedRepo.lastSyncSha,
          }
        : null,
      defaultBranch,
      repositories: repos.map((r) => ({
        id: r.id,
        name: r.name,
        owner: r.owner,
        defaultBranch: r.defaultBranch,
        repoUrl: r.repoUrl,
        lastSyncSha: r.lastSyncSha,
      })),
      preferences,
      security: {
        authProvider: "Clerk (JWT RS256)",
        authenticatedIdentity: user.email || user.name || "Authenticated Developer",
        credentialStorage: "Server-side environment / encrypted vault",
        frontendSecretsExposed: false,
        repoAccessControl: "Per-user UUID scoped row-level security",
        transportEncryption: "TLS 1.3 / HTTPS enforced",
        dataRetentionPolicy: "Snapshot artifacts isolated in private ephemeral storage",
      },
    };
  },

  /**
   * Persist updates to workspace name, preferences, and selected repository default branch.
   */
  async updateSettings(clerkUserId, data = {}) {
    const user = await this._resolveUser(clerkUserId);
    const workspace = await this._getOrCreateDefaultWorkspace(user);
    const repos = await repositoryRepository.findManyByUserId(user.id);

    let currentPrefs = this._parsePreferences(workspace.description);

    if (data.preferences) {
      currentPrefs = {
        ...currentPrefs,
        ...data.preferences,
      };
    }

    if (data.selectedRepositoryId !== undefined) {
      currentPrefs.selectedRepositoryId = data.selectedRepositoryId;
    }
    if (data.defaultBranch !== undefined) {
      currentPrefs.defaultBranch = data.defaultBranch;
    }

    const projectUpdate = {};
    if (data.workspaceName !== undefined) {
      projectUpdate.name = data.workspaceName.trim();
    }
    if (data.workspaceDescription !== undefined) {
      projectUpdate.description = data.workspaceDescription;
    } else {
      projectUpdate.description = JSON.stringify(currentPrefs);
    }

    await projectRepository.update(workspace.id, user.id, projectUpdate);

    // If defaultBranch or selected repo was updated, reflect on the repository row
    const targetRepoId = data.selectedRepositoryId || currentPrefs.selectedRepositoryId;
    if (targetRepoId && data.defaultBranch) {
      const repo = repos.find((r) => r.id === targetRepoId);
      if (repo) {
        await repositoryRepository.update(repo.id, user.id, {
          defaultBranch: data.defaultBranch.trim(),
        });
      }
    }

    return this.getSettings(clerkUserId);
  },
};

export default settingsService;
