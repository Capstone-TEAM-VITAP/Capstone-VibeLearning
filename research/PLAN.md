# Paper alignment plan

Status: draft for author review. Written 2026-11-03 on branch `research/paper-eval`.

## 1. What the product actually is

CodeAI helps people understand a repository they did not write. The shipped pipeline:

1. Mirror a GitHub repo, snapshot a commit.
2. Static analysis (Tree-sitter, **JavaScript/JSX only**) produces a Graph IR: files, symbols, imports, calls, architecture roles.
3. A heuristic context retriever (`findRelevantContext`, `chat.service.js`) selects files and code excerpts for a question.
4. An LLM answers repo questions (chat) or writes multiple-choice quizzes (learning), each with path/line citations. An offline fallback builds simple "which file defines X" questions when no LLM key is set.

The old paper (`Researchpaper.typ`) is about a different system (graph path pruning, RRF, Python parsing) that is not in this codebase. It is retired. The new paper describes only what the code does.

## 2. Working title and thesis

**Grounded Repository Understanding: structure-aware context for question answering and quiz generation over unfamiliar codebases** (title is provisional).

Thesis, stated so it can be false: *Giving the LLM context chosen with a static-analysis graph yields more correct and more verifiably cited answers about a repository than giving it context chosen by lexical search alone.*

If the measurements do not support this, the paper reports that, and the contribution becomes the benchmark and the negative result.

## 3. Research questions and experiments

| RQ | Question | Systems compared | Metrics |
|----|----------|------------------|---------|
| RQ1 | Does graph-aware context selection find the right files? | (a) CodeAI `findRelevantContext`; (b) BM25 over file text; (c) symbol-name grep; (d) random files; (e) optionally a real code-embedding retriever | Hit@k, Recall@k, MRR, nDCG@k with k in {3,5,7} |
| RQ2 | Do better contexts give better chat answers? | Same LLM, fixed model and temperature 0, with context from (a), (b), or none | Answer correctness vs gold rubric; citation validity; hallucinated-path rate |
| RQ3 | Are generated quiz questions valid and grounded? | CodeAI LLM quizzes vs offline fallback vs LLM with no context | Parse validity; citation path/line validity; answer supported by cited lines (human audit on a sample, LLM judge calibrated on it); duplicate rate; answer-position balance |
| RQ4 | How accurate and robust is the static analysis? | CodeAI analyzer vs independent oracles (e.g. TypeScript compiler API or `madge`/`dependency-cruiser` for imports) | Import-resolution precision/recall; symbol-extraction recall; crash rate; runtime vs repo size |
| RQ5 (optional) | Does it help people? | Pilot with 10-20 students: CodeAI vs plain GitHub browsing | Task success, time, quiz pre/post gain |

RQ5 is the only route to a claim about learning. Without it the paper must not say "improves learning" or "personalized". It can say "supports" in the motivation only.

## 4. Benchmark design

- 8-10 public repositories at pinned commit SHAs (JS/JSX/Node/React, 50-1500 files), plus this repo for development only.
- About 20 questions per repo, four types: locate ("where is X handled"), trace ("how does a request reach Y"), dependency ("what depends on Z"), concept ("what does module M do").
- Gold labels are relevant files plus a short rubric answer. Candidate questions may be LLM-drafted; **gold must be verified by humans**, ideally two annotators, with agreement reported (Cohen's kappa).
- Split: development (this repo and 2 others, used to tune weights) and test (the rest, touched once).
- The dataset and scripts are released with the paper.

Why this addresses the old paper's flaws: multiple repos, held-out test set, gold not derived from the system under test, and real baselines.

## 5. Claims we can and cannot make

Can make (once measured): retrieval and answer-quality differences, citation validity rates, analyzer accuracy on JS/JSX, the benchmark, the failure analysis.

Cannot make without more work: multi-language support (analyzer parses JS/JSX only; scanner tags `.py/.ts/.java` but no parser exists), learning-outcome claims, personalization claims, generalization beyond JS web repos.

## 6. Known issues found while preparing this plan

1. **Native crash with the newest Tree-sitter.** `tree-sitter` 0.26.0 raised a Windows access violation while analyzing the frontend (JSX). 0.25.2 works. `requirements.txt` was unpinned; it is now pinned to `tree-sitter==0.25.2` and `tree-sitter-javascript==0.25.0`. All 829 tests pass either way, so the tests did not catch it.
2. **Scanner fails on a pnpm junction.** Scanning a working tree containing `node_modules/.ignored_*` raised `WinError 1920`. The scanner stats entries before applying the ignore rules. Production avoids it by analyzing git-archive snapshots, but it should be fixed and counted in RQ4's robustness numbers.
3. **Embedding module is a stub.** `retrieval/` (chunker, index, hash-based embedder) is not called by the backend. It cannot support any retrieval claim as it stands.
4. **Offline quiz fallback is trivial** ("which file defines X"). Report it as a baseline, not a contribution.

## 7. Work packages

1. Harness (`research/`): benchmark schema, repo pinning script, metric functions with unit tests, one command that regenerates every table from raw outputs.
2. Implement baselines (BM25, grep, random; embeddings optional) behind one retriever interface; run CodeAI's retriever from Node unchanged.
3. Build and verify the benchmark (needs human annotation time).
4. Run RQ1 (no LLM needed), then RQ2/RQ3 (LLM; log model ID, temperature, date, seed, raw responses).
5. RQ4 oracle comparison.
6. Rewrite `Researchpaper.typ` from the recorded results, with exact tests, effect sizes and confidence intervals, and a threats-to-validity section.
7. Housekeeping: LICENSE, CITATION.cff, correct author list, reference check.

## 8. Decisions needed from the authors

- Approve cloning ~10 public repositories for the benchmark (network download).
- Which LLM and key to use for RQ2/RQ3, and a spending cap. The repo's `.env` has provider keys; I have not read their values.
- Who annotates gold labels, and is a user-study pilot (RQ5) feasible before the deadline?
- Target venue, which sets page limit and how strong the claims must be.
