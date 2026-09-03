import { useState } from "react";
import { connectRepo } from "../services/api.js";

function RepoConnectForm({ getToken, onConnected }) {
  const [repoUrl, setRepoUrl] = useState("");
  const [defaultBranch, setDefaultBranch] = useState("main");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const repo = await connectRepo(getToken, {
        repoUrl: repoUrl.trim(),
        ...(defaultBranch.trim() ? { defaultBranch: defaultBranch.trim() } : {}),
      });
      setRepoUrl("");
      onConnected?.(repo);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="repo-form" data-testid="repo-connect-form" onSubmit={handleSubmit}>
      <h3>Connect a GitHub repository</h3>
      <div className="repo-form-row">
        <input
          className="repo-input"
          data-testid="repo-url-input"
          type="text"
          placeholder="https://github.com/owner/repo"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          required
        />
        <input
          className="repo-input repo-input-branch"
          data-testid="repo-branch-input"
          type="text"
          placeholder="main"
          value={defaultBranch}
          onChange={(e) => setDefaultBranch(e.target.value)}
        />
        <button className="btn-sign-up" data-testid="repo-connect-btn" type="submit" disabled={busy}>
          {busy ? "Connecting…" : "Connect"}
        </button>
      </div>
      {error && (
        <p className="repo-error" data-testid="repo-connect-error">
          {error}
        </p>
      )}
    </form>
  );
}

export default RepoConnectForm;
