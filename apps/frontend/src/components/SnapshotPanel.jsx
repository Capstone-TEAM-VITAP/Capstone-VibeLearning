import { useEffect, useState } from "react";
import { getChangedFiles, getDiff, listSnapshots } from "../services/api.js";

const STATUS_LABEL = { A: "added", M: "modified", D: "deleted", R: "renamed", C: "copied" };

function SnapshotPanel({ getToken, repo }) {
  const [snapshots, setSnapshots] = useState([]);
  const [selectedSha, setSelectedSha] = useState(null);
  const [files, setFiles] = useState(null);
  const [diff, setDiff] = useState(null);
  const [showDiff, setShowDiff] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // NOTE: parent passes key={repo.id}, so switching repos remounts this
  // panel with fresh initial state — no reset logic needed here.
  useEffect(() => {
    let cancelled = false;
    listSnapshots(getToken, repo.id).then(
      (rows) => {
        if (cancelled) return;
        setSnapshots(rows);
        if (rows.length) setSelectedSha(rows[0].commitSha);
      },
      (err) => {
        if (!cancelled) setError(err.message);
      }
    );
    return () => {
      cancelled = true;
    };
  }, [getToken, repo]);

  useEffect(() => {
    if (!repo || !selectedSha || files?.headSha === selectedSha) return;
    let cancelled = false;
    getChangedFiles(getToken, repo.id, selectedSha).then(
      (data) => {
        if (!cancelled) {
          setFiles(data);
          setError(null);
        }
      },
      (err) => {
        if (!cancelled) setError(err.message);
      }
    );
    return () => {
      cancelled = true;
    };
  }, [getToken, repo, selectedSha, files]);

  async function handleToggleDiff() {
    if (showDiff) {
      setShowDiff(false);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const data = await getDiff(getToken, repo.id, selectedSha);
      setDiff(data);
      setShowDiff(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!repo) return null;

  const selected = snapshots.find((s) => s.commitSha === selectedSha);

  return (
    <div className="snapshot-panel" data-testid="snapshot-panel">
      <h3>
        Snapshots · {repo.owner}/{repo.name}
      </h3>

      {snapshots.length > 1 && (
        <select
          className="repo-input"
          data-testid="snapshot-select"
          value={selectedSha || ""}
          onChange={(e) => {
            setSelectedSha(e.target.value);
            setShowDiff(false);
            setDiff(null);
          }}
        >
          {snapshots.map((s) => (
            <option key={s.commitSha} value={s.commitSha}>
              {s.commitSha.slice(0, 7)} · {s.message || "no message"} ({s.fileCount} files)
            </option>
          ))}
        </select>
      )}

      {selected && (
        <p className="repo-item-meta" data-testid="snapshot-meta">
          {selected.commitSha.slice(0, 7)} · +{selected.additions} −{selected.deletions} ·{" "}
          {selected.authorName || "unknown author"}
        </p>
      )}

      {!files && !error && <p className="repo-empty">Loading…</p>}
      {error && <p className="repo-error">{error}</p>}

      {files && (
        <>
          <ul className="file-list" data-testid="changed-files-list">
            {files.files.map((f) => (
              <li key={f.path} className="file-item" data-testid={`changed-file-${f.path}`}>
                <span className={`file-status file-status-${f.status}`}>{STATUS_LABEL[f.status] || f.status}</span>
                <span className="file-path">{f.path}</span>
              </li>
            ))}
          </ul>

          <button
            className="btn-sign-in"
            type="button"
            onClick={handleToggleDiff}
            disabled={busy}
            data-testid="toggle-diff-btn"
          >
            {showDiff ? "Hide diff" : "View diff"}
          </button>
        </>
      )}

      {showDiff && diff && (
        <div className="diff-view" data-testid="diff-view">
          {diff.files.map((file) => (
            <div key={file.path} className="diff-file">
              <div className="diff-file-header">
                <span className={`file-status file-status-${file.status}`}>{STATUS_LABEL[file.status] || file.status}</span>
                <span className="file-path">{file.path}</span>
                <span className="diff-counts">
                  +{file.additions} −{file.deletions}
                </span>
              </div>
              {(file.hunks || []).map((hunk, i) => (
                <pre key={i} className="diff-hunk">
                  <div className="diff-hunk-header">
                    @@ −{hunk.oldStart} +{hunk.newStart} @@
                  </div>
                  {(hunk.lines || []).map((line, j) => (
                    <div key={j} className={`diff-line diff-line-${line.type}`}>
                      <span className="diff-gutter">
                        {line.type === "add" ? "+" : line.type === "del" ? "−" : " "}
                      </span>
                      {line.text}
                    </div>
                  ))}
                </pre>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default SnapshotPanel;
