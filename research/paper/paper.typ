// Compile: typst compile research/paper/paper.typ
// Every number below is produced by the scripts in research/ (see Appendix A) and
// stored in research/out/*.md. Do not edit numbers by hand; rerun the scripts.

#set document(title: "Content-Aware Context Selection for Repository Question Answering: An Audit and Repair of CodeAI")
#set page(paper: "us-letter", margin: (x: 0.9in, y: 0.85in), numbering: "1")
#set text(font: "New Computer Modern", size: 10.5pt, lang: "en")
#set par(justify: true, leading: 0.66em)
#set heading(numbering: none)
#show heading.where(level: 1): set text(size: 14pt)
#show heading.where(level: 2): set text(size: 11.5pt)
#show table.cell: set text(size: 8.6pt)
#show raw: set text(font: "DejaVu Sans Mono", size: 8.6pt)

#let tbl(caption, body) = figure(body, caption: caption, kind: table, supplement: [Table])

#align(center)[
  #text(size: 17pt, weight: "bold")[Content-Aware Context Selection for Repository Question Answering: An Audit and Repair of CodeAI]
  #v(6pt)
  #text(weight: "bold")[\[Author names and affiliations to be inserted\]]
  #v(2pt)
  #text(style: "italic")[Draft technical report]
]
#line(length: 100%, stroke: 0.5pt + luma(150))

= Abstract

CodeAI is a platform that helps developers understand an unfamiliar GitHub repository. It parses the repository into a static-analysis graph, selects code excerpts for a question, and hands them to a language model that answers with file and line citations or writes quizzes. We audited the first version on a new benchmark of 357 questions over 15 public JavaScript repositories pinned to exact commits, with gold labels taken from the raw source rather than from the system under test. The audit found three problems. The context selector scored symbol names and paths but never read file contents, so it placed a gold file in its top five for only 71.8% of questions on a 170-question test split, against 94.1% for plain BM25. The analyzer resolved no CommonJS `require` imports, leaving six of ten repositories without internal import edges. The offline quiz generator produced duplicate prompts and skewed answer positions. We repaired all three: a BM25-plus-symbol-bonus retriever, `require` extraction, and a stricter quiz generator. On five repositories that were cloned only after the repair was frozen, top-five accuracy rose from 50.4% to 92.9% (paired difference +0.425, 95% CI \[0.331, 0.528\], p < 0.0001). The repaired retriever is statistically indistinguishable from standalone BM25 on those repositories (difference +0.024, \[−0.008, 0.063\]), so the gain comes from reading file content, not from the graph. Import-resolution recall for CommonJS rose from 0.000 to 0.998. We did not evaluate end-to-end answer quality with a language model, and we ran no user study.

= 1. Introduction

Understanding code you did not write is slow. Tools that answer questions about a repository usually retrieve text and let a language model summarise it. CodeAI adds a static-analysis graph (files, symbols, imports, calls, architectural roles) and uses it to choose the excerpts that go into the prompt. Its answers and quizzes carry path and line citations so that a reader can check them.

This paper asks two narrow questions. First, does the shipped context-selection logic find the right files? Second, once it is repaired, does the graph add anything beyond standard text retrieval? Our contributions are:

+ A reproducible benchmark for repository file retrieval: 357 questions, 15 repositories, exact commit SHAs, gold labels derived from raw source by regular expressions (Section 3).
+ An audit of the first version of CodeAI against BM25, a literal-match baseline and a random baseline, with bootstrap intervals and paired permutation tests (Section 5.1).
+ Three repairs, each with before-and-after measurements, including a confirmatory split that was not touched while the repairs were designed (Sections 4 and 5).
+ A measurement of what the graph contributes, which is little for file retrieval once content is searched (Section 5.2).

The first audit was negative and the repair is ordinary: the final retriever is BM25 with a small bonus. We report it because the failure was invisible to the project's 829 unit tests, the fix is cheap, and the benchmark and scripts are reusable.

= 2. System under test

*Static analysis.* A Python service scans a repository, parses JavaScript and JSX with Tree-sitter, extracts symbols and file-level relationships, resolves imports, classifies files into architectural roles and emits a graph (schema 1.0). Other file types are listed but not parsed.

*Context selection (v1).* `findRelevantContext` tokenized the question and scored graph symbols (exact name +10, token in name +5, token in path +3) and files (symbol-containing files got twice the symbol score; keyword-triggered intent rules added fixed bonuses for words such as "auth", "route", "db"; each query token found in a path added 4). It returned the top seven files and never read file contents when scoring. One rule gave +15 to any path containing "ai" whenever the query contained the substring "ai", which also occurs in "main" and "again".

*Generation.* The selected excerpts go into a prompt for a language model (chat), or an offline routine builds "In which file is X defined?" questions from graph symbols when no model is available.

We evaluate context selection directly. We evaluate the offline quiz generator with deterministic checks. We do not evaluate the language model's final text.

= 3. Benchmark

*Repositories.* Fifteen public JavaScript repositories at pinned commits, in three groups.
- *Development* (3 repositories, 60 questions): `hackathon-starter`, `koa`, `react-redux-realworld-example-app`. Used to choose the one tunable weight.
- *Test* (7 repositories, 170 questions): `express`, `hapi`, `axios`, `react-boilerplate`, `node-fetch`, `passport`, `connect`. We ran the v1 audit on this split. Because we saw its results before designing the repair, it is a post-hoc test of the repair.
- *Confirmatory* (5 repositories, 127 questions): `request`, `winston`, `mocha`, `redux-saga`, `body-parser`. These were cloned after the repair was frozen, and no retriever had been run on them. This is the split that supports the headline claim.

Repositories were chosen by the authors, not sampled.

*Question types.* Gold labels come from regular expressions over raw source, not from the Tree-sitter graph, so the analyzer cannot grade itself. Block comments and whole-line comments are stripped first, so JSDoc such as `{import('./x')}` is not read as a dependency.

- *Locate.* The query is the first sentence of a JSDoc comment on a function, class or assigned function in a non-test file. The gold is the file containing that comment. Descriptions that contain the identifier name, or that occur more than once in a repository, are dropped, so a query cannot be answered by matching a name.
- *Dependency.* "Which files import X?" for a file X with 2 to 15 importers. The gold is the set of importing files found by scanning `require`, `import ... from` and `import()` with relative specifiers. The named file is removed from every system's ranking.

At most 30 locate and 15 dependency questions are kept per repository, chosen by a SHA-1 ordering.

*Metrics.* Hit\@k (a gold file appears in the top k), MRR and nDCG over the top seven results. Intervals are 95% percentile bootstrap intervals (10,000 resamples, fixed seed). Paired comparisons use per-question differences with a sign-flip permutation test (exact for 18 or fewer non-zero differences, otherwise 200,000 seeded draws).

= 4. Compared systems and repairs

- *CodeAI v1*: the original `findRelevantContext`, run unchanged (a copy of the pre-change file is kept in `research/legacy/`) on graphs from the original analyzer.
- *CodeAI v2*: the repaired product code. File ranking is BM25 (k1 = 1.2, b = 0.75) over file content and path tokens with camelCase splitting, plus 0.25 times the best fraction of a symbol name's tokens found in the query, over symbols the analyzer found in the file. The weight 0.25 was the best of {0, 0.1, 0.25, 0.5, 1} on the development split (nDCG 0.783, 0.821, 0.857, 0.853, 0.808). Questions about architecture or structure keep the v1 entrypoint-oriented selection. The "ai" rule now matches whole words. Without a snapshot directory the code falls back to v1.
- *BM25*: an independent implementation of the same ranking without the symbol bonus.
- *Literal match*: files ranked by how many distinct query words occur as substrings of the text or path.
- *Random*: a seeded shuffle.

Two further repairs were made outside retrieval. The relationship extractor now records `require("./x")` with a single string argument as a module-level import, which the existing resolver turns into a file-to-file edge. The offline quiz generator now skips names defined in more than one file, names shorter than three characters and repeated names, and cycles the correct answer through positions A to D. All systems search the same file universe: the files in the analyzer's graph. The test suites grew from 829 to 835 (analyzer) and from 65 to 75 (backend) tests, and the research metrics have their own tests.

= 5. Results

== 5.1 Retrieval before and after (RQ1)

#tbl([File retrieval on the confirmatory split (n = 127: 79 locate, 48 dependency). Brackets are 95% bootstrap intervals.])[
  #table(
    columns: (1.5fr, 1fr, 1fr, 1fr, 1fr),
    align: (left, center, center, center, center),
    stroke: 0.4pt + luma(170),
    table.header[System][Hit\@1][Hit\@5][MRR][nDCG],
    [CodeAI v1], [0.252 \[0.181, 0.331\]], [0.504 \[0.417, 0.591\]], [0.334 \[0.265, 0.405\]], [0.343 \[0.277, 0.410\]],
    [CodeAI v2], [0.740 \[0.661, 0.819\]], [0.929 \[0.882, 0.969\]], [0.814 \[0.756, 0.869\]], [0.823 \[0.768, 0.875\]],
    [BM25], [0.724 \[0.646, 0.803\]], [0.906 \[0.850, 0.953\]], [0.803 \[0.743, 0.861\]], [0.817 \[0.762, 0.868\]],
    [Literal match], [0.535 \[0.449, 0.622\]], [0.882 \[0.827, 0.937\]], [0.682 \[0.618, 0.745\]], [0.733 \[0.675, 0.789\]],
    [Random], [0.024 \[0.000, 0.055\]], [0.079 \[0.031, 0.126\]], [0.046 \[0.020, 0.079\]], [0.039 \[0.018, 0.066\]],
  )
]

On the confirmatory split, v2 improves Hit\@5 over v1 by +0.425 (\[0.331, 0.528\], p < 0.0001), MRR by +0.480 (\[0.385, 0.569\]) and nDCG by +0.480 (\[0.399, 0.559\]). The gain is large for both question types: for locate questions Hit\@5 rises from 0.468 to 0.987, and for dependency questions from 0.563 to 0.833 (+0.271, \[0.083, 0.438\], p = 0.010 for the paired difference measured from v1).

#tbl([File retrieval on the 170-question post-hoc test split, the split on which the v1 audit was run.])[
  #table(
    columns: (1.5fr, 1fr, 1fr, 1fr, 1fr),
    align: (left, center, center, center, center),
    stroke: 0.4pt + luma(170),
    table.header[System][Hit\@1][Hit\@5][MRR][nDCG],
    [CodeAI v1], [0.371 \[0.300, 0.447\]], [0.718 \[0.647, 0.782\]], [0.508 \[0.447, 0.570\]], [0.520 \[0.463, 0.578\]],
    [CodeAI v2], [0.829 \[0.771, 0.882\]], [0.959 \[0.929, 0.982\]], [0.888 \[0.847, 0.926\]], [0.869 \[0.830, 0.904\]],
    [BM25], [0.806 \[0.747, 0.865\]], [0.941 \[0.906, 0.976\]], [0.863 \[0.817, 0.905\]], [0.855 \[0.812, 0.894\]],
    [Literal match], [0.482 \[0.406, 0.559\]], [0.871 \[0.818, 0.918\]], [0.639 \[0.583, 0.694\]], [0.705 \[0.656, 0.753\]],
    [Random], [0.018 \[0.000, 0.041\]], [0.071 \[0.035, 0.112\]], [0.040 \[0.020, 0.065\]], [0.031 \[0.017, 0.046\]],
  )
]

The v1 audit result stands on this split: v1 was far below BM25 (Hit\@5 0.718 against 0.941; paired difference −0.224, 95% CI \[−0.306, −0.141\], p < 0.0001). The reason is a design choice. The v1 scorer read symbol names and paths and did not read file contents, while the locate queries paraphrase documentation that never appears in a name. v2 improves Hit\@5 by +0.241 here (\[0.165, 0.318\], p < 0.0001). The development split gives the same picture (v1 0.600, v2 1.000), though v2's weight was tuned there.

*Per-repository variation.* v2 matches or beats v1 in Hit\@5 on 14 of 15 repositories. The exception is `hapi` (n = 11, all dependency questions), where v1 scored 1.000 and v2 0.727, while BM25 scored only 0.364; there v1's path rules happened to suit the questions. Small repositories carry little weight (`connect` has 3 questions, `request` 4, `body-parser` 8). The full per-repository table is in `research/out/rq1_tables.md`.

*Whole-word rule.* The substring "ai" appears in 40 of the 357 queries but the word itself in only 4, so the old rule fired on 36 queries by accident.

== 5.2 Does the graph help? (exploratory)

On the confirmatory split v2 and BM25 are not distinguishable: Hit\@5 +0.024 (\[−0.008, 0.063\], p = 0.375), MRR +0.011 (\[−0.024, 0.044\], p = 0.542), nDCG +0.006 (\[−0.021, 0.033\], p = 0.660). The same holds on the post-hoc split (Hit\@5 +0.018, \[−0.006, 0.047\], p = 0.375; nDCG +0.014, \[−0.009, 0.038\], p = 0.246). The symbol bonus helped on the development split (nDCG 0.783 without it, 0.857 with it), which is where its weight was chosen, but that effect did not reproduce on fresh repositories. We therefore make no claim that graph symbols improve file retrieval. The justification for keeping the bonus is only that it does no measurable harm and that it makes the retriever consistent with the graph the product already builds. The graph's value is more plausibly in other roles (excerpt windows around symbols, architecture summaries, role labels) that this benchmark does not test.

== 5.3 Analyzer accuracy and robustness (RQ4)

We compared the file-to-file import edges with an oracle built from regular expressions over the source with comments removed, restricted to relative specifiers that resolve to a file in the repository.

#tbl([Import-resolution recall against the regex oracle, pooled over 15 repositories.])[
  #table(
    columns: (2fr, 1fr, 1fr, 1fr),
    align: (left, center, center, center),
    stroke: 0.4pt + luma(170),
    table.header[Import style][Oracle pairs][Recall before][Recall after],
    [ES modules (`import`)], [1,057], [0.986 (10 repos)], [0.980],
    [CommonJS (`require`)], [462], [0.000 (10 repos)], [0.998],
  )
]

The "before" column was measured on the original 10 repositories (694 ES pairs, 276 CommonJS pairs); the "after" column is pooled over all 15, so the two ES figures are not on identical data. Precision was at least 0.987 in every repository with edges and 1.000 in all but two. The remaining ES misses are almost all `export ... from` re-exports (11 of the 12 misses in `redux-saga`), which the graph records as exports, not imports. Analysis took between 0.1 s (77 nodes) and 5.4 s (2,486 nodes) and no repository failed. An unpinned install picked up Tree-sitter 0.26.0, which raised a native access violation on JSX files in the project's own frontend; the dependency is now pinned to 0.25.2. The unit-test suite passed under both versions and did not detect the crash.

An earlier version of the oracle counted `import('./x')` written inside JSDoc type annotations as dependencies, which made the analyzer look worse on `mocha` (0.854 recall) than it was (0.992). We found this by inspecting the apparent misses and corrected the oracle, then rebuilt the question set; one dependency question was removed as a result. We mention it because it was a change made after seeing results, although it only removed false positives.

== 5.4 Offline quiz generation (RQ3, deterministic part)

We generated up to ten offline questions per repository and checked each against the raw source.

#tbl([Offline quiz checks, before and after the generator change.])[
  #table(
    columns: (2fr, 1fr, 1fr),
    align: (left, center, center),
    stroke: 0.4pt + luma(170),
    table.header[Check][Before (10 repos, 100 questions)][After (15 repos, 148 questions)],
    [Cited file contains the symbol], [100 of 100], [148 of 148],
    [Duplicate prompts within a repository], [8], [0],
    [Names of two characters or fewer], [3], [0],
    [Answer positions A / B / C / D], [41 / 21 / 19 / 19], [near-uniform (3/2/2/3 per 10)],
  )
]

Citation consistency was always perfect, which is expected because the questions are built from the same graph; it shows consistency, not educational quality. Names defined in several files, which have no single correct answer, are now excluded, so a question can no longer have an ambiguous key. One repository (`passport`) yields eight questions rather than ten because few symbols remain unique. We did not evaluate language-model-written quizzes or chat answers.

= 6. Threats to validity and limitations

+ *Benchmark scope.* Fifteen JavaScript repositories chosen by the authors; results may not carry over to other languages, larger systems, or TypeScript.
+ *Question realism.* Locate queries are documentation sentences and dependency queries are structured. Neither covers open-ended conceptual questions such as "how does authentication work?", where the retained v1 architecture rules were designed to help.
+ *Gold quality.* Labels are automatic. We spot-checked a sample by eye but ran no human audit and measured no annotator agreement. Test and example directories are excluded for locate questions; other noise, such as a comment detached from the code it describes, remains.
+ *Benchmark favours text search.* The locate task rewards matching words in file content. This is a fair test of whether a context selector can find where something is implemented, but it does not show that BM25 answers every kind of repository question.
+ *Post-hoc design.* The repair was designed after the v1 audit on the 170-question split. The confirmatory split guards against that, but its five repositories are few, and the weight and fallback rules were set before it was run only by our own record.
+ *Multiple comparisons.* We report many paired tests without correction; treat borderline p-values as exploratory.
+ *End-to-end quality.* We measured which files are retrieved, not whether the final text is correct, faithfully cited or useful. We ran no user study, so we make no claim about learning or onboarding.

= 7. Conclusion

An audit of the first CodeAI context selector on a held-out benchmark showed that scoring symbol names and paths, without reading file contents, finds a gold file in the top five only 71.8% of the time on the audit split, against 94.1% for BM25. Replacing it with content-aware ranking raised top-five accuracy on five fresh repositories from 50.4% to 92.9%. The graph symbol bonus added no measurable benefit beyond BM25 there. The analyzer repair for CommonJS imports raised recall from 0 to 0.998, and the quiz generator repair removed duplicates and balanced answer positions. These changes are small, but they address defects that unit tests did not catch. Whether better retrieval improves answers and learning remains untested.

= References

+ S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 and beyond," Foundations and Trends in Information Retrieval, vol. 3, no. 4, pp. 333–389, 2009.
+ G. V. Cormack, C. L. A. Clarke and S. Buettcher, "Reciprocal rank fusion outperforms Condorcet and individual rank learning methods," in Proc. 32nd ACM SIGIR, pp. 758–759, 2009.
+ P. Lewis et al., "Retrieval-augmented generation for knowledge-intensive NLP tasks," in Advances in Neural Information Processing Systems 33, 2020.
+ F. Zhang et al., "RepoCoder: Repository-level code completion through iterative retrieval and generation," in Proc. EMNLP, 2023.
+ T. Liu, C. Xu and J. McAuley, "RepoBench: Benchmarking repository-level code auto-completion systems," in Proc. ICLR, 2024.
+ B. Efron and R. J. Tibshirani, An Introduction to the Bootstrap. Chapman and Hall/CRC, 1994.
+ Tree-sitter, an incremental parsing system for programming tools, https://tree-sitter.github.io/tree-sitter/.

= Appendix A: Reproduction

From the repository root on the `research/paper-eval` branch. Pinned commits are in `research/repos.json`.

```text
bash research/scripts/fetch_repos.sh
cd apps/ai-service && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python ../../research/scripts/analyze_repos.py            # v2 graphs -> out/graphs
# v1 graphs: run the same script with AI_SERVICE_DIR pointing at a copy of src/ whose
# repository/relationships.py is the pre-change version, and OUT_SUBDIR=v1
cd ../../research
node src/build_questions.mjs        # data/questions.json
node --test test/metrics.test.mjs   # metric unit tests
node src/run_rq1.mjs                # out/rq1_tables.md, out/rq1_raw.json
node src/run_rq4.mjs                # out/rq4_import_accuracy.md
node src/run_rq3_offline.mjs        # out/rq3_offline.md
```

Pinned commits: express 43fca52, koa b7ead6f, hapi 9358b48, axios 7324e94, hackathon-starter fb53b17, react-redux-realworld-example-app ee72eba, react-boilerplate d19099a, node-fetch 8b3320d, passport 217018d, connect 98ab0c4, request 3c0cddc, winston ff0b79d, mocha 5b5afa7, redux-saga 85d1218, body-parser 67d27df.
