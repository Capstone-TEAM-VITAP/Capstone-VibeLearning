import { useCallback, useEffect, useState } from "react";
import {
  generateLearningSet,
  getLearningSet,
  listLearningSets,
  submitLearningAnswers,
  getLearningProgress,
} from "../services/api.js";
import Blocks from "./Blocks.jsx";
import {
  Bot,
  Check,
  CircleCheck,
  CircleX,
  FileText,
  FolderX,
  GraduationCap,
  Info,
  Lightbulb,
  ListChecks,
  Pointer,
  Sparkles,
  Terminal,
  Trophy,
  Workflow,
} from "lucide-react";
import Button from "./ui/button.jsx";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "./ui/card.jsx";
import { Input, Select } from "./ui/input.jsx";
import Badge from "./ui/badge.jsx";
import { Progress } from "./ui/progress.jsx";
import "./LearningView.css";

const DIFFICULTIES = ["beginner", "intermediate", "advanced"];
const OPTION_LETTERS = ["A", "B", "C", "D"];

const DIFFICULTY_BADGE = {
  beginner: "success",
  intermediate: "warning",
  advanced: "destructive",
};

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
  const answeredCount = activeSet?.questions?.filter((q) => picks[q.id] != null).length || 0;
  const scorePct = result && result.total ? Math.round((result.correct / result.total) * 100) : 0;

  if (!selectedRepo) {
    return (
      <div className="learning-workspace" data-testid="learning-empty">
        <Card className="learning-empty-card">
          <CardContent className="learning-empty-body">
            <FolderX size={40} className="learning-empty-icon" />
            <h3>No repository selected</h3>
            <p>Connect a repository to generate personalized quizzes from its code.</p>
            <Button type="button" onClick={() => setView?.("repos")}>
              <Workflow size={16} />
              Open Repositories
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="learning-workspace" data-testid="learning-view">
      <div className="learning-hero">
        <div className="learning-hero-text">
          <Badge>
            <GraduationCap size={14} />
            Developer Learning
          </Badge>
          <h1 className="learning-title">Learn {repoName}</h1>
          <p className="learning-subtitle">
            Generate MCQ quizzes grounded in the analyzed codebase. Same topic + difficulty returns the saved set.
          </p>
        </div>
        {progress && (
          <Card className="learning-progress-card" data-testid="learning-progress">
            <div className="learning-progress-stats">
              <div className="learning-stat">
                <span className="learning-stat-value">{progress.sets}</span>
                <span className="learning-stat-label">sets</span>
              </div>
              <div className="learning-stat">
                <span className="learning-stat-value">{progress.answered}/{progress.total}</span>
                <span className="learning-stat-label">answered</span>
              </div>
              <div className="learning-stat">
                <span className="learning-stat-value learning-stat-good">{progress.correct}</span>
                <span className="learning-stat-label">correct</span>
              </div>
            </div>
            <Progress value={progress.answered} max={Math.max(progress.total, 1)} />
          </Card>
        )}
      </div>

      {error && (
        <div className="learning-error" data-testid="learning-error" role="alert">
          <CircleX size={16} />
          <span>{error}</span>
          {needsAnalysis && (
            <Button type="button" size="sm" variant="secondary" onClick={() => setView?.("analysis")}>
              Run analysis
            </Button>
          )}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>
            <Sparkles size={16} />
            New quiz
          </CardTitle>
          <CardDescription>Pick a topic from this repository and generate grounded questions.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="learning-generator" onSubmit={handleGenerate}>
            <label className="learning-field learning-field-grow">
              <span className="learning-label">Topic</span>
              <Input
                data-testid="learning-topic"
                placeholder="e.g. authentication"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                maxLength={200}
              />
            </label>
            <label className="learning-field">
              <span className="learning-label">Difficulty</span>
              <Select
                data-testid="learning-difficulty"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
              >
                {DIFFICULTIES.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </Select>
            </label>
            <label className="learning-field learning-field-narrow">
              <span className="learning-label">Questions</span>
              <Select
                data-testid="learning-count"
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
              >
                {[3, 5, 8, 10].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </Select>
            </label>
            <Button
              type="submit"
              data-testid="learning-generate"
              disabled={generating}
              className="learning-generate-btn"
            >
              {generating ? (
                <>
                  <Blocks size={16} />
                  Generating…
                </>
              ) : (
                <>
                  <ListChecks size={16} />
                  Generate quiz
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="learning-columns">
        <section className="learning-sets" aria-label="Quiz sets">
          <div className="learning-sets-head">
            <h3>Quiz sets</h3>
            <Badge variant="secondary">{sets.length}</Badge>
          </div>
          {sets.length === 0 ? (
            <Card className="learning-sets-empty">
              <CardContent className="learning-sets-empty-body">
                <ListChecks size={32} />
                <p>No quizzes yet. Generate one above.</p>
              </CardContent>
            </Card>
          ) : (
            <ul>
              {sets.map((s) => {
                const done = s.progress?.total
                  ? s.progress.answered >= s.progress.total && s.progress.total > 0
                  : false;
                return (
                  <li key={s.id}>
                    <button
                      type="button"
                      data-testid={`learning-set-${s.id}`}
                      className={`learning-set-card ${s.id === activeSetId ? "active" : ""}`}
                      onClick={() => setActiveSetId(s.id)}
                    >
                      <span className="learning-set-top">
                        <strong>{s.topic}</strong>
                        {done && (
                          <CircleCheck size={14} className="learning-set-done" title="Completed" />
                        )}
                      </span>
                      <span className="learning-set-meta">
                        <Badge variant={DIFFICULTY_BADGE[s.difficulty] || "secondary"}>
                          {s.difficulty}
                        </Badge>
                        <span>{s.questionCount} questions</span>
                      </span>
                      {s.progress && (
                        <span className="learning-set-progress">
                          <Progress value={s.progress.answered} max={Math.max(s.progress.total, 1)} />
                          <span>{s.progress.answered}/{s.progress.total} answered</span>
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="learning-quiz" aria-label="Quiz solver">
          {loadingSet ? (
            <Card>
              <CardContent className="learning-loading-panel">
                <Blocks size={40} />
                <p>Loading quiz…</p>
              </CardContent>
            </Card>
          ) : !activeSet ? (
            <Card className="learning-quiz-empty">
              <CardContent className="learning-quiz-empty-body">
                <Pointer size={32} />
                <p>Select a quiz set to solve it here.</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <div className="learning-quiz-head">
                  <CardTitle>{activeSet.topic}</CardTitle>
                  <div className="learning-quiz-badges">
                    <Badge variant={DIFFICULTY_BADGE[activeSet.difficulty] || "secondary"}>
                      {activeSet.difficulty}
                    </Badge>
                    {activeSet.engine && (
                      <Badge
                        variant="outline"
                        data-testid="learning-engine"
                        title={activeSet.engine === "llm" ? "Generated by the configured LLM" : "Generated offline from code symbols"}
                      >
                        {activeSet.engine === "llm" ? <Bot size={13} /> : <Terminal size={13} />}
                        {activeSet.engine}
                      </Badge>
                    )}
                  </div>
                </div>
                <CardDescription>
                  {answeredCount}/{activeSet.questions?.length || 0} answered
                </CardDescription>
              </CardHeader>
              <CardContent>
                {result && (
                  <div className="learning-score" data-testid="learning-score">
                    <Trophy size={22} />
                    <strong>Score: {result.correct}/{result.total}</strong>
                    <span className="learning-score-pct">{scorePct}%</span>
                  </div>
                )}
                <ol className="learning-questions">
                  {(activeSet.questions || []).map((q, idx) => {
                    const graded = result?.results?.find((r) => r.questionId === q.id);
                    return (
                      <li key={q.id} className="learning-question" data-testid={`learning-q-${q.id}`}>
                        <p className="learning-question-prompt">
                          <Badge variant="secondary" className="learning-qnum">Q{idx + 1}</Badge>
                          {q.prompt}
                        </p>
                        <div className="learning-options" role="radiogroup" aria-label={q.prompt}>
                          {(q.options || []).map((opt, oi) => {
                            const selected = picks[q.id] === oi;
                            const isAnswer = graded && oi === graded.answerIndex;
                            const isWrongPick = graded && !graded.correct && selected;
                            return (
                              <button
                                key={oi}
                                type="button"
                                role="radio"
                                aria-checked={selected}
                                disabled={submitting}
                                onClick={() => setPicks((p) => ({ ...p, [q.id]: oi }))}
                                className={[
                                  "learning-option",
                                  selected && !graded ? "selected" : "",
                                  isAnswer ? "correct" : "",
                                  isWrongPick ? "wrong" : "",
                                ].filter(Boolean).join(" ")}
                              >
                                <span className="learning-option-letter">{OPTION_LETTERS[oi]}</span>
                                <span>{opt}</span>
                                {isAnswer && (
                                  <CircleCheck size={16} className="learning-option-icon" />
                                )}
                                {isWrongPick && (
                                  <CircleX size={16} className="learning-option-icon" />
                                )}
                              </button>
                            );
                          })}
                        </div>
                        {q.citationPath && (
                          <p className="learning-citation">
                            <FileText size={15} />
                            {q.citationPath}{q.citationStart != null ? `:${q.citationStart}` : ""}
                          </p>
                        )}
                        {graded && (
                          <p className={`learning-explanation ${graded.correct ? "good" : "bad"}`}>
                            {graded.correct ? <Lightbulb size={17} /> : <Info size={17} />}
                            <span>
                              {graded.correct ? "Correct" : `Correct answer: ${OPTION_LETTERS[graded.answerIndex]}`} — {graded.explanation || q.explanation || ""}
                            </span>
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ol>
              </CardContent>
              <CardFooter>
                <Button
                  type="button"
                  data-testid="learning-submit"
                  onClick={handleSubmit}
                  disabled={submitting}
                >
                  {submitting ? (
                    <>
                      <Blocks size={16} />
                      Submitting…
                    </>
                  ) : (
                    <>
                      <Check size={16} />
                      Submit answers
                    </>
                  )}
                </Button>
              </CardFooter>
            </Card>
          )}
        </section>
      </div>
    </div>
  );
}

export default LearningView;
