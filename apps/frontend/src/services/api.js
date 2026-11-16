const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:5000/api/v1";

export async function getCurrentUser(getToken) {
  const token = await getToken();

  const response = await fetch(`${API_URL}/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch current user");
  }

  return response.json();
}

async function authedFetch(getToken, path, options = {}) {
  const token = await getToken();

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });

  if (response.status === 204) return null;

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(body.message || `Request failed (${response.status})`);
  }

  return body;
}

// --- Connected repositories (GitHub ingest pipeline) ---

export async function listRepos(getToken) {
  const body = await authedFetch(getToken, "/repos");
  return body.data;
}

export async function connectRepo(getToken, payload) {
  const body = await authedFetch(getToken, "/repos/connect", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return body.data;
}

export async function syncRepo(getToken, id, payload = {}) {
  const body = await authedFetch(getToken, `/repos/${id}/sync`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return body.data;
}

export async function deleteRepo(getToken, id) {
  await authedFetch(getToken, `/repos/${id}`, { method: "DELETE" });
  return true;
}

export async function listSnapshots(getToken, id) {
  const body = await authedFetch(getToken, `/repos/${id}/snapshots`);
  return body.data;
}

export async function getChangedFiles(getToken, id, sha, base) {
  const query = base ? `?base=${encodeURIComponent(base)}` : "";
  const body = await authedFetch(getToken, `/repos/${id}/snapshots/${sha}/files${query}`);
  return body.data;
}

export async function getDiff(getToken, id, sha, base) {
  const query = base ? `?base=${encodeURIComponent(base)}` : "";
  const body = await authedFetch(getToken, `/repos/${id}/snapshots/${sha}/diff${query}`);
  return body.data;
}

// --- Analysis jobs (demo: stub engine until ai-service lands) ---

export async function analyzeSnapshot(getToken, id, sha) {
  const body = await authedFetch(getToken, `/repos/${id}/snapshots/${sha}/analyze`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  return body.data;
}

export async function getAnalysis(getToken, id, sha) {
  const body = await authedFetch(getToken, `/repos/${id}/snapshots/${sha}/analysis`);
  return body.data;
}

export async function getSnapshotGraph(getToken, id, sha) {
  const body = await authedFetch(getToken, `/repos/${id}/snapshots/${sha}/graph`);
  return body.data || body;
}

// --- Repository AI Assistant ---

export async function askRepoQuestion(getToken, id, message, history = []) {
  const body = await authedFetch(getToken, `/repos/${id}/chat`, {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
  return body.data;
}

// --- Developer Learning (MCQ quizzes) ---

export async function generateLearningSet(getToken, id, payload) {
  const body = await authedFetch(getToken, `/repos/${id}/learning/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return body.data;
}

export async function generateDiffLearningSet(getToken, id, payload) {
  const body = await authedFetch(getToken, `/repos/${id}/learning/generate-diff`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return body.data;
}

export async function listLearningSets(getToken, id) {
  const body = await authedFetch(getToken, `/repos/${id}/learning/sets`);
  return body.data;
}

export async function getLearningSet(getToken, id, setId) {
  const body = await authedFetch(getToken, `/repos/${id}/learning/sets/${setId}`);
  return body.data;
}

export async function submitLearningAnswers(getToken, id, setId, answers) {
  const body = await authedFetch(getToken, `/repos/${id}/learning/sets/${setId}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
  return body.data;
}

export async function getLearningProgress(getToken, id) {
  const body = await authedFetch(getToken, `/repos/${id}/learning/progress`);
  return body.data;
}