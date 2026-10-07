import { useCallback, useEffect, useState } from "react";
import {
  generateLearningSet,
  getLearningSet,
  listLearningSets,
  submitLearningAnswers,
  getLearningProgress,
} from "../services/api.js";
import "./LearningView.css";

const DIFFICULTIES = ["beginner", "intermediate", "advanced"];

function LearningView({ getToken, selectedRepo, setView }) {
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("beginner");
  const [count, setCount] = useState(5);
  const [sets, setSets] = useState([]);
  const [activeSetId, setActiveSetId] = useState(null);
  const [activeSet, setActiveSet] = useState(null);
  const [picks, setPicks] = useState({});
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [loadingSet, setLoadingSet] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const repoId = selectedRepo?.id || null;
  const repoName = selectedRepo ? `${selectedRepo.owner}/${selectedRepo.name}` : null;

  const refreshLists = useCallback(async () => {
    if (!repoId) {
      setSets([]);
      setProgress(null);
      return;
    }
    try {
      const [rows, prog] = await Promise.all([
        listLearningSets(getToken, repoId),
        getLearningProgress(getToken, repoId).catch(() => null),
      ]);
      setSets(Array.isArray(rows) ? rows : []);
      if (prog) setProgress(prog);
    } catch (err) {
      setError(err.message);
    }
  }, [getToken, repoId]);

  useEffect(() => {
    setActiveSetId(null);
    setActiveSet(null);
    setPicks({});
    setResult(null);
    setError(null);
    refreshLists();
  }, [refreshLists]);

  useEffect(() => {
    if (!repoId || !activeSetId) {
      setActiveSet(null);
      return;
    }
    let cancelled = false;
    setLoadingSet(true);
    setError(null);
    getLearningSet(getToken, repoId, activeSetId).then(
      (s) => {
        if (cancelled) return;
        setActiveSet(s);
        const initial = {};
        for (const q of s.questions || []) {
          if (q.attempt?.pickedIndex != null) initial[q.id] = q.attempt.pickedIndex;
        }
        setPicks(initial);
        setResult(null);
      },
      (err) => {
        if (!cancelled) setError(err.message);
      },
    ).finally(() => {
      if (!cancelled) setLoadingSet(false);
    });
    return () => {
      cancelled = true;
    };
  }, [getToken, repoId, activeSetId]);

  async function handleGenerate(e) {
    e?.preventDefault();
    if (!repoId) {
      setError("Please connect or select a repository first.");
      return;
    }
    const cleanTopic = topic.trim();
    if (!cleanTopic) {
      setError("Topic is required.");
      return;
    }
    setGenerating(true);
    setError(null);
    setResult(null);
    try {
      const created = await generateLearningSet(getToken, repoId, {
        topic: cleanTopic,
        difficulty,
        count: Number(count),
      });
      await refreshLists();
      if (created?.id) {
        setActiveSetId(created.id);
        setActiveSet(created);
        setPicks({});
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  async function handleSubmit() {
    if (!repoId || !activeSetId || !activeSet?.questions?.length) return;
    const answers = activeSet.questions
      .filter((q) => picks[q.id] != null)
      .map((q) => ({ questionId: q.id, pickedIndex: picks[q.id] }));
    if (!answers.length) {
      setError("Select at least one answer before submitting.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitLearningAnswers(getToken, repoId, activeSetId, answers);
      setResult(res);
      await refreshLists();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const needsAnalysis = error && /not enough repository context|run analysis first/i.test(error);

  if (!selectedRepo) {
    return (
      <div className="intel-notice-card" data-testid="learning-empty">
        <div className="intel-notice-icon">
          <span className="material-symbols-outlined">folder_off</span>
        </div>
        <h3>No repository selected</h3>
        <p>Connect a repository to generate personalized quizzes from its code.</p>
        <button type="button" className="ws-btn ws-btn-primary" onClick={() => setView?.("repos")}>
          Open Repositories
        </button>
      </div>
    );
  }

  return (
    <div className="learning-workspace" data-testid="learning-view">
      <div className="learning-hero">
        <div>
          <span className="intel-hero-eyebrow">
            <span className="material-symbols-outlined">school</span>
            Developer Learning
          </span>
          <h1 className="intel-hero-title">Learn {repoName}</h1>
          <p className="intel-hero-desc">
            Generate MCQ quizzes grounded in the analyzed codebase. Same topic + difficulty returns the saved set.
          </p>
        </div>
        {progress && (
          <div className="learning-progress" data-testid="learning-progress">
            <span>{progress.sets} sets</span>
            <span>·</span>
            <span>{progress.answered}/{progress.total} answered</span>
            <span>·</span>
            <span>{progress.correct} correct</span>
          </div>
        )}
      </div>

      {error && (
        <div className="learning-error" data-testid="learning-error">
          <span className="material-symbols-outlined">error</span>
          <span>{error}</span>
          {needsAnalysis && (
            <button type="button" className="ws-btn ws-btn-secondary" onClick={() => setView?.("analysis")}>
              Run analysis
            </button>
          )}
        </div>
      )}

      <form className="learning-generator" onSubmit={handleGenerate}>
        <input
          className="repo-input learning-topic"
          data-testid="learning-topic"
          placeholder="Topic, e.g. authentication"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          maxLength={200}
        />
        <select
          className="repo-input"
          data-testid="learning-difficulty"
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value)}
        >
          {DIFFICULTIES.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select
          className="repo-input"
          data-testid="learning-count"
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
        >
          {[3, 5, 8, 10].map((n) => (
            <option key={n} value={n}>{n} questions</option>
          ))}
        </select>
        <button
          type="submit"
          className="ws-btn ws-btn-primary"
          data-testid="learning-generate"
          disabled={generating}
        >
          {generating ? "Generating…" : "Generate quiz"}
        </button>
      </form>

      <div className="learning-columns">
        <div className="learning-sets">
          <h3>Quiz sets ({sets.length})</h3>
          {sets.length === 0 ? (
            <p className="repo-empty">No quizzes yet. Generate one above.</p>
          ) : (
            <ul>
              {sets.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    data-testid={`learning-set-${s.id}`}
                    className={`learning-set-item ${s.id === activeSetId ? "active" : ""}`}
                    onClick={() => setActiveSetId(s.id)}
                  >
                    <strong>{s.topic}</strong>
                    <span>{s.difficulty} · {s.questionCount}q</span>
                    {s.progress && (
                      <span>{s.progress.answered}/{s.progress.total} answered</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="learning-quiz">
          {loadingSet ? (
            <p className="repo-empty">Loading quiz…</p>
          ) : !activeSet ? (
            <p className="repo-empty">Select a quiz set to solve it here.</p>
          ) : (
            <>
              {activeSet.engine && (
                <p className="repo-item-meta" data-testid="learning-engine">
                  Engine: {activeSet.engine}
                </p>
              )}
              <ol className="learning-questions">
                {(activeSet.questions || []).map((q, idx) => {
                  const graded = result?.results?.find((r) => r.questionId === q.id);
                  return (
                    <li key={q.id} className="learning-question" data-testid={`learning-q-${q.id}`}>
                      <p><strong>Q{idx + 1}.</strong> {q.prompt}</p>
                      <div className="learning-options">
                        {(q.options || []).map((opt, oi) => (
                          <label key={oi} className={`learning-option ${graded ? (oi === graded.answerIndex ? "correct" : (picks[q.id] === oi ? "wrong" : "")) : ""}`}>
                            <input
                              type="radio"
                              name={q.id}
                              checked={picks[q.id] === oi}
                              onChange={() => setPicks((p) => ({ ...p, [q.id]: oi }))}
                              disabled={submitting}
                            />
                            {opt}
                          </label>
                        ))}
                      </div>
                      {q.citationPath && (
                        <p className="repo-item-meta">{q.citationPath}{q.citationStart != null ? `:${q.citationStart}` : ""}</p>
                      )}
                      {graded && (
                        <p className={`repo-item-meta ${graded.correct ? "" : "repo-error"}`}>
                          {graded.correct ? "Correct" : `Correct answer: ${graded.answerIndex + 1}`} — {graded.explanation || q.explanation || ""}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ol>
              <div className="learning-actions">
                <button
                  type="button"
                  className="ws-btn ws-btn-primary"
                  data-testid="learning-submit"
                  onClick={handleSubmit}
                  disabled={submitting}
                >
                  {submitting ? "Submitting…" : "Submit answers"}
                </button>
                {result && (
                  <span data-testid="learning-score">Score: {result.correct}/{result.total}</span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default LearningView;
