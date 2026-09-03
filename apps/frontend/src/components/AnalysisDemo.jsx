import { useEffect, useState } from "react";
import {
  analyzeSnapshot,
  getAnalysis,
  listRepos,
  listSnapshots,
} from "../services/api.js";

const IMPACT_LABEL = { high: "high impact", medium: "medium impact", low: "low impact" };

/**
 * Demo page for the analysis pipeline (stub engine until ai-service lands).
 * Pick repo -> pick snapshot -> run analysis -> poll job -> render result.
 */
function AnalysisDemo({ getToken }) {
  const [repos, setRepos] = useState([]);
  const [repoId, setRepoId] = useState("");
  const [snapshots, setSnapshots] = useState([]);
  const [sha, setSha] = useState("");
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listRepos(getToken).then(
      (rows) => {
        if (cancelled) return;
        setRepos(rows);
        if (rows.length && !repoId) setRepoId(rows[0].id);
      },
      (err) => {
        if (!cancelled) setError(err.message);
      }
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken]);

  useEffect(() => {
    if (!repoId) return;
    let cancelled = false;
    listSnapshots(getToken, repoId).then(
      (rows) => {
        if (cancelled) return;
        setSnapshots(rows);
        if (rows.length) setSha(rows[0].commitSha);
      },
      (err) => {
        if (!cancelled) setError(err.message);
      }
    );
    return () => {
      cancelled = true;
    };
  }, [getToken, repoId]);

  useEffect(() => {
    if (!repoId || !sha) return;
    let cancelled = false;
    let timer = null;
    const stop = () => {
      if (timer) clearInterval(timer);
      timer = null;
    };
    const load = () =>
      getAnalysis(getToken, repoId, sha).then(
        (j) => {
          if (cancelled) return;
          setJob(j);
          setError(null);
          if (j.status === "done" || j.status === "failed") stop();
        },
        (err) => {
          if (cancelled) return;
          if (/no analysis/i.test(err.message || "")) {
            setJob(null);
            stop();
          } else {
            setError(err.message);
            stop();
          }
        }
      );
    load();
    timer = setInterval(load, 2000);
    return () => {
      cancelled = true;
      stop();
    };
  }, [getToken, repoId, sha]);

  async function handleAnalyze() {
    setBusy(true);
    setError(null);
    try {
      const j = await analyzeSnapshot(getToken, repoId, sha);
      setJob(j);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const repo = repos.find((r) => r.id === repoId) || null;
  const result = job?.result || null;

  return (
    <div className="profile-box" data-testid="analysis-demo">
      <h3>
        Analysis <span className="brand-badge">demo</span>
      </h3>
      {!repos.length && !error && <p className="repo-empty">Loading…</p>}
      {error && <p className="repo-error">{error}</p>}

      {repos.length > 0 && (
        <div className="repo-form-row">
          <select
            className="repo-input"
            data-testid="analysis-repo-select"
            value={repoId}
            onChange={(e) => {
              setRepoId(e.target.value);
              setSnapshots([]);
              setSha("");
              setJob(null);
            }}
          >
            {repos.map((r) => (
              <option key={r.id} value={r.id}>
                {r.owner}/{r.name}
              </option>
            ))}
          </select>
          {snapshots.length > 0 && (
            <select
              className="repo-input"
              data-testid="analysis-snapshot-select"
              value={sha}
              onChange={(e) => setSha(e.target.value)}
            >
              {snapshots.map((s) => (
                <option key={s.commitSha} value={s.commitSha}>
                  {s.commitSha.slice(0, 7)} · {s.message || "no message"}
                </option>
              ))}
            </select>
          )}
          <button
            className="btn-sign-up"
            type="button"
            data-testid="analysis-run-btn"
            disabled={busy || !sha}
            onClick={handleAnalyze}
          >
            {busy ? "Analyzing…" : "Run analysis"}
          </button>
        </div>
      )}

      {job && job.status !== "done" && (
        <p className="repo-empty" data-testid="analysis-status">
          Job {job.status}… (attempt {job.attempts})
        </p>
      )}
      {job && job.status === "failed" && (
        <p className="repo-error" data-testid="analysis-error">
          {job.error || "Analysis failed"}
        </p>
      )}

      {result && (
        <div data-testid="analysis-result">
          <p className="repo-item-meta">
            {result.summary}{" "}
            <span className="engine-badge" data-testid="analysis-engine">
              {result.engine === "stub" ? "STUB — replace with ai-service" : result.engine}
            </span>
          </p>
          {repo && (
            <p className="repo-item-meta">
              {repo.owner}/{repo.name} @ {sha.slice(0, 7)}
            </p>
          )}
          <ul className="file-list">
            {(result.files || []).map((f) => (
              <li key={f.path} className="file-item">
                <span className={`file-status file-status-${f.status}`}>
                  {f.status === "A" ? "added" : f.status === "M" ? "modified" : f.status === "D" ? "deleted" : f.status}
                </span>
                <span className="file-path">{f.path}</span>
                <span className={`impact-badge impact-${f.impact}`}>
                  {IMPACT_LABEL[f.impact] || f.impact}
                </span>
                <span className="diff-counts">
                  +{f.additions} −{f.deletions}
                </span>
              </li>
            ))}
          </ul>
          {result.note && <p className="repo-item-meta">{result.note}</p>}
        </div>
      )}
    </div>
  );
}

export default AnalysisDemo;
