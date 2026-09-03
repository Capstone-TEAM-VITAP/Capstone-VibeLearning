import { useCallback, useEffect, useState } from "react";
import { deleteRepo, listRepos, syncRepo } from "../services/api.js";
import RepoConnectForm from "./RepoConnectForm.jsx";
import RepoList from "./RepoList.jsx";
import SnapshotPanel from "./SnapshotPanel.jsx";

function ReposSection({ getToken }) {
  const [repos, setRepos] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const rows = await listRepos(getToken);
      setRepos(rows);
      return rows;
    } catch (err) {
      setError(err.message);
      return [];
    }
  }, [getToken]);

  useEffect(() => {
    let cancelled = false;
    listRepos(getToken).then(
      (rows) => {
        if (!cancelled) setRepos(rows);
      },
      (err) => {
        if (!cancelled) setError(err.message);
      }
    );
    return () => {
      cancelled = true;
    };
  }, [getToken]);

  async function handleConnected(repo) {
    const rows = await refresh();
    setSelectedId(repo?.id || rows[0]?.id || null);
  }

  async function handleSync(id) {
    setBusyId(id);
    setError(null);
    try {
      await syncRepo(getToken, id);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(id) {
    setBusyId(id);
    setError(null);
    try {
      await deleteRepo(getToken, id);
      const rows = await refresh();
      if (selectedId === id) setSelectedId(rows[0]?.id || null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  const selected = repos.find((r) => r.id === selectedId) || null;

  return (
    <div className="profile-box" data-testid="repos-section">
      <h3>Connected Repositories</h3>
      {error && <p className="repo-error">{error}</p>}
      <RepoConnectForm getToken={getToken} onConnected={handleConnected} />
      <RepoList
        repos={repos}
        selectedId={selectedId}
        busyId={busyId}
        onSelect={setSelectedId}
        onSync={handleSync}
        onDelete={handleDelete}
      />
      {selected && <SnapshotPanel key={selected.id} getToken={getToken} repo={selected} />}
    </div>
  );
}

export default ReposSection;
