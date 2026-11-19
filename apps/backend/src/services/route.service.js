import { repositoryRepository } from "../repositories/repository.repository.js";
import { snapshotRepository } from "../repositories/snapshot.repository.js";
import { userRepository } from "../repositories/user.repository.js";
import { aiService } from "./ai.service.js";
import { ensureMirror, ensureSnapshotTree } from "./git.service.js";
import { NotFoundError, UnauthorizedError } from "../utils/errors.js";

/**
 * Service for API & Route Map intelligence across repository snapshots.
 */
export const routeService = {
  async _resolveUserAndRepo(clerkUserId, repositoryId) {
    if (!clerkUserId) {
      throw new UnauthorizedError("Authentication required");
    }

    const user = await userRepository.findByClerkId(clerkUserId);
    if (!user) {
      throw new UnauthorizedError("User record not found");
    }

    const repo = await repositoryRepository.findByIdAndUserId(repositoryId, user.id);
    if (!repo) {
      throw new NotFoundError("Repository not found");
    }

    return { user, repo };
  },

  async _resolveSnapshot(repoId, commitSha) {
    const snapshot = await snapshotRepository.findByRepoAndSha(repoId, commitSha);
    if (!snapshot) {
      throw new NotFoundError(`Snapshot '${commitSha}' not found`);
    }
    return snapshot;
  },

  async _ensureSnapshotTree(repo, commitSha, options = {}) {
    // If repo object has mirror configuration, ensure bare mirror is up to date
    if (repo && repo.repoUrl && typeof ensureMirror === "function") {
      try {
        await ensureMirror({
          repositoryId: repo.id,
          repoUrl: repo.repoUrl,
          defaultBranch: repo.defaultBranch || "main",
        });
      } catch (err) {
        console.warn(`[RouteService] Mirror sync warning for ${repo.name}:`, err.message);
      }
    }
    const repoId = repo?.id || repo;
    return ensureSnapshotTree(repoId, commitSha, options);
  },

  /**
   * Fetch and analyze all routes for a given snapshot, applying optional filters.
   */
  async getRoutes(clerkUserId, repositoryId, commitSha, filters = {}) {
    const { repo } = await this._resolveUserAndRepo(clerkUserId, repositoryId);
    const snapshot = await this._resolveSnapshot(repo.id, commitSha);

    const forceRefresh = Boolean(filters.refresh === "true" || filters.refresh === true || filters.rescan);
    const snapshotDir = await this._ensureSnapshotTree(repo, snapshot.commitSha, { force: forceRefresh });

    console.log(`[RouteService] Analyzing routes for repository ${repo.name} (${repo.id}), snapshot: ${snapshot.commitSha}`);
    console.log(`[RouteService] Snapshot directory: ${snapshotDir}`);

    const analysis = await aiService.analyzeRoutes(snapshotDir, repo.name);
    let routes = analysis.routes || [];

    console.log(
      `[RouteService] Discovered ${analysis.summary?.total_endpoints ?? routes.length} endpoints (${analysis.summary?.controllers_count ?? 0} controllers resolved) for ${repo.name}`
    );

    // Filter by HTTP method
    if (filters.method) {
        routes = routes.filter((r) => r.http_method.toUpperCase() === filters.method.toUpperCase());
    }

    // Filter by status (resolved, inline, unresolved)
    if (filters.status) {
        routes = routes.filter((r) => r.status.toLowerCase() === filters.status.toLowerCase());
    }

    // Filter by controller name
    if (filters.controller) {
        routes = routes.filter((r) => r.controller?.name?.toLowerCase().includes(filters.controller.toLowerCase()));
    }

    // Search filter across endpoint, controller, and source file
    if (filters.search) {
        const q = filters.search.toLowerCase();
        routes = routes.filter(
            (r) =>
                r.http_endpoint.toLowerCase().includes(q) ||
                r.controller?.name?.toLowerCase().includes(q) ||
                r.source_file.toLowerCase().includes(q)
        );
    }

    return {
        repositoryName: analysis.repository_name,
        summary: analysis.summary,
        total: routes.length,
        routes,
    };
  },

  /**
   * Return only the summary metrics for discovered endpoints.
   */
  async getRouteSummary(clerkUserId, repositoryId, commitSha, filters = {}) {
    const { repo } = await this._resolveUserAndRepo(clerkUserId, repositoryId);
    const snapshot = await this._resolveSnapshot(repo.id, commitSha);

    const forceRefresh = Boolean(filters.refresh === "true" || filters.refresh === true);
    const snapshotDir = await this._ensureSnapshotTree(repo, snapshot.commitSha, { force: forceRefresh });
    const analysis = await aiService.analyzeRoutes(snapshotDir, repo.name);

    return {
        repositoryName: analysis.repository_name,
        summary: analysis.summary,
    };
  },

  /**
   * Return detailed information for a single route by ID.
   */
  async getRouteById(clerkUserId, repositoryId, commitSha, routeId) {
    const { repo } = await this._resolveUserAndRepo(clerkUserId, repositoryId);
    const snapshot = await this._resolveSnapshot(repo.id, commitSha);

    const snapshotDir = await this._ensureSnapshotTree(repo, snapshot.commitSha);
    const analysis = await aiService.analyzeRoutes(snapshotDir, repo.name);

    const cleanId = decodeURIComponent(routeId).trim();
    const route = (analysis.routes || []).find(
        (r) => r.id === cleanId || r.http_endpoint === cleanId || r.id.endsWith(cleanId)
    );

    if (!route) {
        throw new NotFoundError(`Route '${routeId}' not found`);
    }

    return route;
  },
};

export default routeService;
