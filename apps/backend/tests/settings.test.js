import { test } from "node:test";
import assert from "node:assert/strict";
import { settingsService, DEFAULT_PREFERENCES } from "../src/services/settings.service.js";
import { settingsController } from "../src/controllers/settings.controller.js";

const mockUser1 = { id: "u-1", clerkUserId: "clerk-1", email: "dev1@example.com", name: "Dev One" };
const mockUser2 = { id: "u-2", clerkUserId: "clerk-2", email: "dev2@example.com", name: "Dev Two" };

const mockWorkspace1 = {
  id: "w-1",
  name: "Dev One Workspace",
  description: JSON.stringify(DEFAULT_PREFERENCES),
  userId: "u-1",
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

const mockRepos1 = [
  {
    id: "r-1",
    userId: "u-1",
    name: "repo-alpha",
    owner: "dev1",
    defaultBranch: "main",
    repoUrl: "https://github.com/dev1/repo-alpha",
    lastSyncSha: "a1b2c3d4e5f67890123456789012345678901234",
  },
  {
    id: "r-2",
    userId: "u-1",
    name: "repo-beta",
    owner: "dev1",
    defaultBranch: "develop",
    repoUrl: "https://github.com/dev1/repo-beta",
    lastSyncSha: "b2c3d4e5f67890123456789012345678901234a1",
  },
];

test("settingsService.getSettings returns workspace, repos, preferences, and security without secrets", async () => {
  const origResolve = settingsService._resolveUser;
  const origWorkspace = settingsService._getOrCreateDefaultWorkspace;
  const { repositoryRepository } = await import("../src/repositories/repository.repository.js");
  const origFindRepos = repositoryRepository.findManyByUserId;

  settingsService._resolveUser = async () => mockUser1;
  settingsService._getOrCreateDefaultWorkspace = async () => mockWorkspace1;
  repositoryRepository.findManyByUserId = async () => mockRepos1;

  try {
    const res = await settingsService.getSettings("clerk-1");

    // 1. Workspace
    assert.equal(res.workspace.id, "w-1");
    assert.equal(res.workspace.name, "Dev One Workspace");

    // 2. Repositories
    assert.equal(res.repositories.length, 2);
    assert.equal(res.repositories[0].name, "repo-alpha");

    // 3. Default branch
    assert.equal(res.defaultBranch, "main");

    // 4. Preferences
    assert.equal(res.preferences.theme, "dark");
    assert.equal(res.preferences.autoSync, true);

    // 5. Security - verify no tokens, secrets or keys exposed
    assert.ok(res.security);
    assert.equal(res.security.frontendSecretsExposed, false);
    assert.equal(res.security.authProvider, "Clerk (JWT RS256)");
    const serialized = JSON.stringify(res);
    assert.equal(serialized.includes("token"), false);
    assert.equal(serialized.includes("secret"), false);
    assert.equal(serialized.includes("password"), false);
  } finally {
    settingsService._resolveUser = origResolve;
    settingsService._getOrCreateDefaultWorkspace = origWorkspace;
    repositoryRepository.findManyByUserId = origFindRepos;
  }
});

test("settingsService.updateSettings updates workspace name, default branch, and preferences", async () => {
  const origResolve = settingsService._resolveUser;
  const origWorkspace = settingsService._getOrCreateDefaultWorkspace;
  const { projectRepository } = await import("../src/repositories/project.repository.js");
  const { repositoryRepository } = await import("../src/repositories/repository.repository.js");
  const origUpdateProj = projectRepository.update;
  const origFindRepos = repositoryRepository.findManyByUserId;
  const origUpdateRepo = repositoryRepository.update;

  let capturedProjectUpdate = null;
  let capturedRepoUpdate = null;

  settingsService._resolveUser = async () => mockUser1;
  settingsService._getOrCreateDefaultWorkspace = async () => ({ ...mockWorkspace1 });
  projectRepository.update = async (id, userId, data) => {
    capturedProjectUpdate = { id, userId, data };
    return { ...mockWorkspace1, ...data };
  };
  repositoryRepository.findManyByUserId = async () => mockRepos1;
  repositoryRepository.update = async (id, userId, data) => {
    capturedRepoUpdate = { id, userId, data };
    return { ...mockRepos1[0], ...data };
  };

  try {
    const updated = await settingsService.updateSettings("clerk-1", {
      workspaceName: "Updated Workspace Alpha",
      selectedRepositoryId: "r-1",
      defaultBranch: "develop",
      preferences: {
        theme: "light",
        autoSync: false,
        diffViewMode: "unified",
      },
    });

    assert.equal(capturedProjectUpdate.userId, "u-1");
    assert.equal(capturedProjectUpdate.data.name, "Updated Workspace Alpha");
    assert.match(capturedProjectUpdate.data.description, /"theme":"light"/);
    assert.match(capturedProjectUpdate.data.description, /"autoSync":false/);

    assert.equal(capturedRepoUpdate.id, "r-1");
    assert.equal(capturedRepoUpdate.data.defaultBranch, "develop");
  } finally {
    settingsService._resolveUser = origResolve;
    settingsService._getOrCreateDefaultWorkspace = origWorkspace;
    projectRepository.update = origUpdateProj;
    repositoryRepository.findManyByUserId = origFindRepos;
    repositoryRepository.update = origUpdateRepo;
  }
});

test("settingsService isolates workspaces and repos between different users", async () => {
  const origResolve = settingsService._resolveUser;
  const origWorkspace = settingsService._getOrCreateDefaultWorkspace;
  const { repositoryRepository } = await import("../src/repositories/repository.repository.js");
  const origFindRepos = repositoryRepository.findManyByUserId;

  let requestedUserIds = [];
  settingsService._resolveUser = async (clerkId) => {
    return clerkId === "clerk-1" ? mockUser1 : mockUser2;
  };
  settingsService._getOrCreateDefaultWorkspace = async (user) => {
    requestedUserIds.push(user.id);
    return { ...mockWorkspace1, userId: user.id };
  };
  repositoryRepository.findManyByUserId = async (userId) => {
    return userId === "u-1" ? mockRepos1 : [];
  };

  try {
    const res1 = await settingsService.getSettings("clerk-1");
    assert.equal(res1.repositories.length, 2);

    const res2 = await settingsService.getSettings("clerk-2");
    assert.equal(res2.repositories.length, 0);

    assert.equal(requestedUserIds[0], "u-1");
    assert.equal(requestedUserIds[1], "u-2");
  } finally {
    settingsService._resolveUser = origResolve;
    settingsService._getOrCreateDefaultWorkspace = origWorkspace;
    repositoryRepository.findManyByUserId = origFindRepos;
  }
});

test("settingsController dispatches getSettings and updateSettings with 200", async () => {
  const origGet = settingsService.getSettings;
  const origUpdate = settingsService.updateSettings;

  settingsService.getSettings = async () => ({ workspace: { name: "Test" } });
  settingsService.updateSettings = async () => ({ workspace: { name: "Updated" } });

  try {
    let getResult = null;
    await settingsController.getSettings(
      { userId: "clerk-1" },
      { status: () => ({ json: (data) => { getResult = data; } }) },
      () => {}
    );
    assert.equal(getResult.success, true);
    assert.equal(getResult.data.workspace.name, "Test");

    let updateResult = null;
    await settingsController.updateSettings(
      { userId: "clerk-1", body: { workspaceName: "Updated" } },
      { status: () => ({ json: (data) => { updateResult = data; } }) },
      () => {}
    );
    assert.equal(updateResult.success, true);
    assert.equal(updateResult.data.workspace.name, "Updated");
  } finally {
    settingsService.getSettings = origGet;
    settingsService.updateSettings = origUpdate;
  }
});
