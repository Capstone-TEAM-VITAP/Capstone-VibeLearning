import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";
import { getIntelligenceSummary } from "../services/api.js";
import "./AiSummaryPanel.css";

function timeAgo(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  return hrs < 24 ? `${hrs} h ago` : d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

// Show `backticked` names as code chips instead of literal backticks
function RichText({ text }) {
  const parts = String(text || "").split(/(`[^`]+`)/g);
  return parts.map((part, i) =>
    part.startsWith("`") && part.endsWith("`") && part.length > 2 ? (
      <code key={i}>{part.slice(1, -1)}</code>
    ) : (
      part
    ),
  );
}

/**
 * AI briefing for the current snapshot. The server caches one summary per
 * commit, so opening the page again is instant; "Regenerate" forces a new one.
 */
function AiSummaryPanel({ getToken, repoId, commitSha }) {
  const [state, setState] = useState({ status: "idle", data: null, error: null });
  const requestRef = useRef(0);

  const load = useCallback(
    async (refresh = false) => {
      if (!repoId || !commitSha) return;
      const id = ++requestRef.current;
      setState((s) => ({ status: "loading", data: refresh ? s.data : null, error: null }));
      try {
        const data = await getIntelligenceSummary(getToken, repoId, commitSha, { refresh });
        if (id === requestRef.current) setState({ status: "ready", data, error: null });
      } catch (err) {
        if (id === requestRef.current) setState((s) => ({ status: "error", data: s.data, error: err.message }));
      }
    },
    [getToken, repoId, commitSha],
  );

  useEffect(() => {
    // Fetch (or read the server cache) whenever the repo or commit changes
    load(false);
  }, [load]);

  const { status, data, error } = state;
  const loading = status === "loading";

  return (
    <section className="console-card ai-summary" aria-busy={loading}>
      <div className="console-card-head">
        <h2 className="console-card-title">
          <Sparkles size={14} />
          AI summary
        </h2>
        <div className="ai-summary-head-right">
          {data && !loading && (
            <span className="ai-summary-meta">
              {data.model} · {timeAgo(data.generatedAt)}
            </span>
          )}
          <button
            type="button"
            className="ws-btn ws-btn-ghost"
            onClick={() => load(true)}
            disabled={loading || !commitSha}
            title="Generate a new summary for this commit"
          >
            <RefreshCw size={13} style={loading ? { animation: "spin 1s linear infinite" } : undefined} />
            {loading ? "Generating…" : "Regenerate"}
          </button>
        </div>
      </div>

      {!commitSha ? (
        <p className="ai-summary-note">Analyze the repository to get an AI summary.</p>
      ) : loading && !data ? (
        <div className="ai-summary-loading">
          <p className="ai-summary-note">
            Reading the code graph and writing a summary. This usually takes 20–30 seconds.
          </p>
          <div className="ai-skel" style={{ width: "92%" }} />
          <div className="ai-skel" style={{ width: "78%" }} />
          <div className="ai-skel" style={{ width: "85%" }} />
        </div>
      ) : error && !data ? (
        <div className="ai-summary-error">
          <p>Couldn't generate the summary: {error}</p>
          <button type="button" className="ws-btn ws-btn-secondary" onClick={() => load(false)}>
            Try again
          </button>
        </div>
      ) : data ? (
        <div className={`ai-summary-body ${loading ? "is-refreshing" : ""}`}>
          {error && <p className="ai-summary-inline-error">Regenerate failed: {error}</p>}

          <p className="ai-summary-overview">
            <RichText text={data.overview} />
          </p>

          {data.atAGlance?.length > 0 && (
            <dl className="ai-glance">
              {data.atAGlance.map((f) => (
                <div key={f.label} className="ai-glance-item">
                  <dt>{f.label}</dt>
                  <dd>
                    <RichText text={f.value} />
                  </dd>
                </div>
              ))}
            </dl>
          )}

          <div className="ai-summary-grid">
            {Array.isArray(data.architecture) && data.architecture.length > 0 ? (
              <div className="ai-summary-block ai-summary-block--wide">
                <h3>How it's organised</h3>
                <ul className="ai-kv">
                  {data.architecture.map((a, i) => (
                    <li key={`${a.path || a.area}-${i}`}>
                      <div className="ai-kv-k">
                        <b>{a.area}</b>
                        {a.path && <code>{a.path}</code>}
                      </div>
                      <span className="ai-kv-v">
                        <RichText text={a.description} />
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              typeof data.architecture === "string" &&
              data.architecture && (
                <div className="ai-summary-block ai-summary-block--wide">
                  <h3>How it's organised</h3>
                  <p className="ai-summary-text">
                    <RichText text={data.architecture} />
                  </p>
                </div>
              )
            )}

            {data.keyComponents?.length > 0 && (
              <div className="ai-summary-block ai-summary-block--wide">
                <h3>Key components</h3>
                <ul className="ai-kv">
                  {data.keyComponents.map((c, i) => (
                    <li key={`${c.path}-${i}`}>
                      <div className="ai-kv-k">
                        <b>{c.name}</b>
                        {c.path && <code>{c.path}</code>}
                      </div>
                      <span className="ai-kv-v">
                        <RichText text={c.role} />
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {data.startHere?.length > 0 && (
              <div className="ai-summary-block">
                <h3>Start reading here</h3>
                <ol className="ai-start">
                  {data.startHere.map((s, i) => (
                    <li key={`${s.path}-${i}`}>
                      <code>{s.path}</code>
                      <span>
                        <RichText text={s.why} />
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {data.observations?.length > 0 && (
              <div className="ai-summary-block">
                <h3>What the numbers show</h3>
                <ul className="ai-bullets">
                  {data.observations.map((o, i) => (
                    <li key={i}>
                      <RichText text={o} />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {data.risks?.length > 0 && (
              <div className="ai-summary-block">
                <h3>Risks and gaps</h3>
                <ul className="ai-bullets ai-bullets--risk">
                  {data.risks.map((r, i) => (
                    <li key={i}>
                      <RichText text={r} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <p className="ai-summary-foot">
            Written by AI from the code graph{data.usedReadme ? " and README" : ""} for commit{" "}
            <code>{String(data.commitSha || "").slice(0, 7)}</code>. Check important claims in the code.
          </p>
        </div>
      ) : null}
    </section>
  );
}

export default AiSummaryPanel;
