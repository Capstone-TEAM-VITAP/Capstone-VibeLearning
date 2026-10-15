const $ = (id) => document.getElementById(id);
const repoId = $("repoId");
const repoSelect = $("repositorySelect");
const branchInput = $("branch");
const repoStatus = $("repoStatus");
const results = $("results");

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

$("loadRepos").addEventListener("click", async () => {
  const username = $("username").value.trim();
  if (!username) { repoStatus.textContent = "Enter a GitHub username."; return; }
  repoStatus.textContent = "Loading public repositories…";
  repoSelect.innerHTML = "";
  try {
    const data = await requestJson(`/api/github/repositories?username=${encodeURIComponent(username)}`);
    if (!data.repositories.length) {
      repoSelect.add(new Option("No public repositories found", ""));
      repoStatus.textContent = "No public repositories found.";
      return;
    }
    data.repositories.forEach(repo => {
      const option = new Option(`${repo.full_name}${repo.description ? " — " + repo.description : ""}`, repo.full_name);
      option.dataset.branch = repo.default_branch || "main";
      repoSelect.add(option);
    });
    repoStatus.textContent = `Loaded ${data.repositories.length} public repositories.`;
    repoSelect.dispatchEvent(new Event("change"));
  } catch (error) {
    repoStatus.textContent = error.message;
  }
});

repoSelect.addEventListener("change", () => {
  const selected = repoSelect.selectedOptions[0];
  if (!selected || !selected.value) return;
  const [owner, repo] = selected.value.split("/");
  repoId.value = `github:${owner}/${repo}`;
  branchInput.value = selected.dataset.branch || "main";
});

$("analyzeRepo").addEventListener("click", async () => {
  const fullName = repoSelect.value;
  const branch = branchInput.value.trim();
  if (!fullName || !branch) { repoStatus.textContent = "Choose a repository and branch first."; return; }
  const [owner, repo] = fullName.split("/");
  repoStatus.textContent = "Downloading, parsing, embedding, and indexing…";
  $("analyzeRepo").disabled = true;
  try {
    const data = await requestJson("/api/github/analyze", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({owner, repo, branch})
    });
    repoId.value = data.repository_id;
    repoStatus.textContent = `Indexed ${data.chunks_indexed} chunks across ${data.languages.join(", ")}.`;
  } catch (error) {
    repoStatus.textContent = error.message;
  } finally {
    $("analyzeRepo").disabled = false;
  }
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}

function renderResults(data) {
  if (!data.results || !data.results.length) {
    results.innerHTML = `<div class="empty"><span>⌕</span><h3>No matches found</h3><p>Index the repository first or try a different query.</p></div>`;
    return;
  }
  results.innerHTML = data.results.map((item, index) => `
    <article class="result-card">
      <div class="result-head">
        <div><div class="result-title">${index + 1}. ${escapeHtml(item.symbol || "Code chunk")}</div>
        <div class="meta">${escapeHtml(item.file)} · ${escapeHtml(item.language || "unknown")} · lines ${escapeHtml(item.start_line ?? "?")}-${escapeHtml(item.end_line ?? "?")}</div></div>
        <div class="score">score ${Number(item.hybrid_score ?? item.semantic_score ?? 0).toFixed(3)}</div>
      </div>
      <pre>${escapeHtml(item.code)}</pre>
    </article>`).join("");
}

async function runSearch(query) {
  const repository_id = repoId.value.trim();
  if (!repository_id) { results.textContent = "Enter a repository ID."; return; }
  results.innerHTML = `<div class="empty"><h3>Searching…</h3><p>Finding relevant code chunks.</p></div>`;
  $("searchButton").disabled = true;
  try {
    const data = await requestJson("/search", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({repository_id, query, limit: 5})
    });
    renderResults(data);
  } catch (error) {
    results.innerHTML = `<div class="empty"><h3>Search failed</h3><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    $("searchButton").disabled = false;
  }
}

$("searchForm").addEventListener("submit", event => {
  event.preventDefault();
  const query = $("query").value.trim();
  if (query) runSearch(query);
});
document.querySelectorAll(".suggestion").forEach(button => {
  button.addEventListener("click", () => {
    $("query").value = button.textContent;
    runSearch(button.textContent);
  });
});
