import { execFile } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { BadRequestError } from "../utils/errors.js";
import { mergeChangedFiles, parseNameStatus, parseUnifiedDiff } from "../utils/diff.js";

const execFileAsync = promisify(execFile);

const GIT_TIMEOUT_MS = 30000;
const GIT_MAX_BUFFER = 10 * 1024 * 1024;
const SHA_RE = /^[0-9a-f]{40}$/i;
const EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904";

/**
 * Base directory for bare-mirror caches. One mirror per Repository row.
 */
export function getCacheDir() {
  return process.env.GIT_CACHE_DIR || path.join(os.tmpdir(), "codeai-repos");
}

export function getMirrorDir(repositoryId) {
  return path.join(getCacheDir(), String(repositoryId));
}

/**
 * Parse a GitHub repo URL into owner/name + canonical https URL.
 * Accepts https + ssh forms, with/without .git suffix.
 */
export function parseRepoUrl(repoUrl) {
  const input = String(repoUrl || "").trim();
  if (!input) throw new BadRequestError("repoUrl is required");

  let owner;
  let name;

  const https = input.match(/^https?:\/\/([^/]+)\/([^/\s]+)\/([^/\s]+?)(?:\.git)?\/?$/i);
  if (https) {
    if (https[1].toLowerCase() !== "github.com") {
      throw new BadRequestError("Only github.com repositories are supported");
    }
    owner = https[2];
    name = https[3];
  } else {
    const ssh = input.match(/^git@([^:]+):([^/\s]+)\/([^/\s]+?)(?:\.git)?\/?$/i);
    if (!ssh) throw new BadRequestError("repoUrl must be a GitHub repo URL (https or ssh)");
    if (ssh[1].toLowerCase() !== "github.com") {
      throw new BadRequestError("Only github.com repositories are supported");
    }
    owner = ssh[2];
    name = ssh[3];
  }

  if (!/^[\w.-]+$/.test(owner) || !/^[\w.-]+$/.test(name)) {
    throw new BadRequestError("Invalid GitHub owner or repository name");
  }

  return {
    owner,
    name,
    normalizedUrl: `https://github.com/${owner}/${name}`,
  };
}

/**
 * Build a clone URL, injecting a token for private repos without persisting it.
 * Token never leaves this module's spawned args and is stripped from errors.
 */
export function buildAuthenticatedUrl(normalizedUrl, accessToken) {
  if (!accessToken) return normalizedUrl;
  const token = String(accessToken).trim();
  if (!token) return normalizedUrl;
  if (/[\s@]/.test(token)) throw new BadRequestError("Invalid access token format");
  return normalizedUrl.replace("https://", `https://x-access-token:${token}@`);
}

export function stripSecrets(message) {
  return String(message || "").replace(/x-access-token:[^@\s]+@/g, "x-access-token:<redacted>@");
}

async function runGit(args, options = {}) {
  try {
    return await execFileAsync("git", args, {
      timeout: GIT_TIMEOUT_MS,
      maxBuffer: GIT_MAX_BUFFER,
      ...options,
    });
  } catch (err) {
    err.message = stripSecrets(err.message);
    if (err.stderr) err.stderr = stripSecrets(err.stderr);
    if (err.stdout) err.stdout = stripSecrets(String(err.stdout).slice(0, 2000));
    throw err;
  }
}

function toGitError(err, fallback) {
  const stderr = stripSecrets(err.stderr || err.stdout || err.message || "");
  const msg = stderr.split("\n").filter(Boolean).slice(0, 3).join(" ").slice(0, 300);
  return new BadRequestError(msg || fallback);
}

/**
 * Clone (mirror) or fetch the repo into the local cache.
 */
export async function ensureMirror({ repositoryId, repoUrl, accessToken, defaultBranch = "main" }) {
  const { normalizedUrl } = parseRepoUrl(repoUrl);
  const remoteUrl = buildAuthenticatedUrl(normalizedUrl, accessToken);
  const dir = getMirrorDir(repositoryId);
  fs.mkdirSync(getCacheDir(), { recursive: true });

  try {
    if (!fs.existsSync(dir)) {
      await runGit(["clone", "--mirror", remoteUrl, dir]);
    } else {
      await runGit(["--git-dir", dir, "remote", "set-url", "origin", remoteUrl]);
      await runGit(["--git-dir", dir, "fetch", "--prune", "origin"]);
    }
  } catch (err) {
    // Remove half-cloned dir so the next sync retries cleanly
    try {
      const probe = await runGit(["--git-dir", dir, "rev-parse", "--git-dir"]).catch(() => null);
      if (!probe) fs.rmSync(dir, { recursive: true, force: true });
    } catch {
      // ignore cleanup errors
    }
    throw toGitError(err, `Unable to fetch ${normalizedUrl}. Check the URL and access token.`);
  }

  return { dir, normalizedUrl, defaultBranch };
}

/**
 * Resolve a branch/sha ref to a full 40-char commit sha.
 */
export async function resolveSha(repositoryId, ref) {
  const dir = getMirrorDir(repositoryId);
  const candidates = ref ? [ref] : [];
  // Fall back through common default-branch refs for bare mirrors
  candidates.push("origin/HEAD", "origin/main", "origin/master", "HEAD");
  let lastErr = null;
  for (const candidate of candidates) {
    try {
      const { stdout } = await runGit(["--git-dir", dir, "rev-parse", "--verify", `${candidate}^{commit}`]);
      const sha = stdout.trim();
      if (SHA_RE.test(sha)) return sha;
    } catch (err) {
      lastErr = err;
    }
  }
  throw toGitError(lastErr || new Error("ref not found"), `Unable to resolve ref '${ref || "default branch"}'`);
}

/**
 * Commit metadata for snapshot rows.
 */
export async function getCommitMeta(repositoryId, sha) {
  const dir = getMirrorDir(repositoryId);
  try {
    const { stdout } = await runGit([
      "--git-dir",
      dir,
      "log",
      "-1",
      "--format=%H%n%s%n%an%n%cI",
      sha,
    ]);
    const [fullSha, subject, authorName, committedAt] = stdout.split("\n").map((s) => s.trim());
    return { commitSha: fullSha, message: subject || null, authorName: authorName || null, committedAt: committedAt || null };
  } catch (err) {
    throw toGitError(err, `Unable to read commit ${sha}`);
  }
}

/**
 * List files changed between two commits (three-dot range with two-dot fallback).
 */
export async function getChangedFiles(repositoryId, baseSha, headSha) {
  const dir = getMirrorDir(repositoryId);
  if (!baseSha) {
    const { stdout } = await runGit(["--git-dir", dir, "ls-tree", "-r", "--name-only", headSha]).catch((err) => {
      throw toGitError(err, `Unable to list files at ${headSha}`);
    });
    return stdout.split("\n").map((s) => s.trim()).filter(Boolean).map((p) => ({ path: p, status: "A" }));
  }
  const ranges = [`${baseSha}...${headSha}`, `${baseSha}..${headSha}`];
  let output = null;
  let lastErr = null;
  for (const range of ranges) {
    try {
      const res = await runGit(["--git-dir", dir, "diff", "--name-status", "--no-renames", range]);
      output = res.stdout;
      break;
    } catch (err) {
      lastErr = err;
    }
  }
  if (output === null) throw toGitError(lastErr || new Error("diff failed"), "Unable to compute changed files");
  return parseNameStatus(output);
}

/**
 * Full diff (hunks + totals) between two commits.
 */
export async function getSnapshotDiff(repositoryId, baseSha, headSha, paths = []) {
  const dir = getMirrorDir(repositoryId);
  const from = baseSha || EMPTY_TREE_SHA;
  const args = ["--git-dir", dir, "diff", "--unified=3", "--no-color", "--no-ext-diff", `${from}`, headSha, "--"];
  if (paths.length) args.push(...paths);
  let stdout;
  try {
    ({ stdout } = await runGit(args));
  } catch (err) {
    throw toGitError(err, "Unable to compute diff");
  }
  const hunksByFile = parseUnifiedDiff(stdout);
  const nameStatus = baseSha
    ? parseNameStatus((await runGit(["--git-dir", dir, "diff", "--name-status", "--no-renames", `${baseSha}..${headSha}`]).catch(() => ({ stdout: "" }))).stdout)
    : hunksByFile.map((f) => ({ path: f.path, status: "A" }));
  const files = mergeChangedFiles(nameStatus.length ? nameStatus : hunksByFile.map((f) => ({ path: f.path, status: "A" })), hunksByFile);
  const additions = files.reduce((n, f) => n + f.additions, 0);
  const deletions = files.reduce((n, f) => n + f.deletions, 0);
  return { baseSha: baseSha || null, headSha, fileCount: files.length, additions, deletions, files };
}

export default {
  getCacheDir,
  getMirrorDir,
  parseRepoUrl,
  buildAuthenticatedUrl,
  stripSecrets,
  ensureMirror,
  resolveSha,
  getCommitMeta,
  getChangedFiles,
  getSnapshotDiff,
};
