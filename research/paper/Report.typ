// Compile: typst compile research/paper/Report.typ
// Every number is produced by the scripts in research/ (Appendix D) and stored in research/out/*.md.
// Tables: paper/tables.typ (make_tables.py). Figures: paper/figures (make_figures.py, make_diagrams.py).

#set document(title: "CodeAI: When Does Code Structure Help? An Empirical Study of Lexical, Neural and Graph Retrieval for Repository Questions")
#set page(paper: "us-letter", margin: (x: 0.9in, y: 0.85in), numbering: "1")
#set text(font: "New Computer Modern", size: 10.5pt, lang: "en")
#set par(justify: true, leading: 0.66em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): set text(size: 14pt)
#show heading.where(level: 2): set text(size: 11.5pt)
#show heading.where(level: 3): set text(size: 10.5pt)
#show table.cell: set text(size: 8.4pt)
#show table: set par(justify: false)
#show raw: set text(font: "DejaVu Sans Mono", size: 8.4pt)
#show outline.entry.where(level: 1): set text(weight: "bold")

#import "tables.typ": v1-tests, repo-table, retrieval-heldout, retrieval-other, leak-table, overlap-table, flows-held-out, pruner-sensitivity, fusion-sweep, k-table, significance-table, product-tests, product-before-after, accuracy, n-dropped
#let tbl(caption, body) = figure(body, caption: caption, kind: table, supplement: [Table])
#let plain-table = (cols, head, ..rows) => table(
  columns: cols, align: left, stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),
  table.header(..head), ..rows,
)

// Front pages (title, certificate, acknowledgement, abstract) follow the
// VIT-AP Capstone thesis sample format: Times New Roman, centred headings.
#let front-heading(title, outlined: true) = align(center, text(size: 14pt)[
  #heading(numbering: none, outlined: outlined)[#title]
])

// ---- Title page (unnumbered; counts as page 1) ----
#page(numbering: none)[
  #set text(font: "Times New Roman", size: 12pt)
  #set par(justify: false)
  #align(center)[
    #v(0in)
    #text(size: 16pt, weight: "bold")[CODEAI: WHEN DOES CODE STRUCTURE HELP?]
    #v(2pt)
    #text(size: 13pt, weight: "bold")[An Empirical Study of Lexical, Neural and Graph Retrieval for Repository Questions]
    #v(18pt)
    #text(weight: "bold")[A CAPSTONE PROJECT REPORT]
    #v(14pt)
    Submitted in partial fulfillment of the \
    requirement for the award of the \
    Degree of
    #v(12pt)
    #text(weight: "bold")[BACHELOR OF TECHNOLOGY \ IN \ COMPUTER SCIENCE & ENGINEERING]
    #v(12pt)
    by
    #v(6pt)
    #text(size: 14pt, weight: "bold")[
      Thanmay Gowda B J (23BCE7238) \
      Shrijeet Ambastha (23BCE8158) \
      Bondge Shreeniwas Sanjay (23BCE7176) \
      Kundan Kumar Dubey (23BCE8447)
    ]
    #v(12pt)
    Under the Guidance of
    #v(6pt)
    #text(weight: "bold")[DR. NGANGBAM INDRASON]
    #v(16pt)
    #image("figures/vitap-logo.jpg", width: 2.3in)
    #v(12pt)
    #text(size: 14pt)[
      SCHOOL OF COMPUTER SCIENCE AND ENGINEERING \
      VIT-AP UNIVERSITY, AMARAVATI- 522237
      #v(10pt)
      NOVEMBER 2026
    ]
  ]
]

#[
#set text(font: "Times New Roman", size: 12pt)

// ---- Certificate ----
#front-heading([CERTIFICATE], outlined: false)
#v(14pt)
#text(size: 14pt)[This is to certify that the Capstone Project work titled *CodeAI: When Does Code Structure Help? An Empirical Study of Lexical, Neural and Graph Retrieval for Repository Questions* that is being submitted by Thanmay Gowda B J (23BCE7238), Shrijeet Ambastha (23BCE8158), Bondge Shreeniwas Sanjay (23BCE7176), and Kundan Kumar Dubey (23BCE8447) is in partial fulfillment of the requirements for the award of Bachelor of Technology, is a record of bonafide work done under my guidance. The contents of this Project work, in full or in parts, have neither been taken from any other source nor have been submitted to any other Institute or University for award of any degree or diploma and the same is certified.]
#v(0.9in)
#align(right, text(size: 14pt)[Dr. Ngangbam Indrason \ *Guide*])
#v(0.5in)
#align(center)[
  *The thesis is satisfactory / unsatisfactory*
  #v(0.8in)
  #grid(columns: (1fr, 1fr), [*Examiner 1*], [*Examiner 2*])
  #v(0.4in)
  *Approved by*
  #v(0.8in)
  Dr. G. Muneeswari \
  HoD, Department of Data Science and Engineering \
  School of Computer Science and Engineering (SCOPE)\
  VIT-AP University, Amaravati, Andhra Pradesh
]
#pagebreak()

// ---- Acknowledgement ----
#front-heading([ACKNOWLEDGEMENT])
#v(8pt)
#set par(spacing: 1.2em)
We would like to express our sincere gratitude to VIT-AP University, Amaravati, Andhra Pradesh, for providing us with the opportunity, infrastructure, and academic environment to undertake and successfully complete our Capstone Project.

We are deeply grateful to Dr. G. Viswanathan, Chancellor, VIT-AP University, and Dr. P. Arulmozhivarman, Vice-Chancellor, VIT-AP University, for their visionary leadership, encouragement, and commitment to providing quality education and fostering innovation and research.

We express our sincere thanks to Dr. S. Sudhakar Ilango, Dean, SCOPE, and Dr. Saroj Kumar Panigrahy, Associate Dean, SCOPE, for the continuous encouragement, academic support, and facilities provided throughout the project.

We are profoundly grateful to Dr. Ngangbam Indrason, our Project Supervisor/Guide, for the invaluable guidance, constant support, constructive feedback, and encouragement extended to us at every stage of this project. Their expertise and suggestions have been instrumental in the successful completion of our work.

We would also like to extend our sincere appreciation to all the faculty members and staff of the School of Computer Science and Engineering for their cooperation, valuable suggestions, and support during the course of this project.

Finally, we express our heartfelt gratitude to our parents, family members, and friends for their constant encouragement, patience, and support throughout our academic journey.

#v(10pt)
Project Team Members: \
Thanmay Gowda B J – 23BCE7238 \
Bondge Shreeniwas Sanjay – 23BCE7176 \
Shrijeet Ambastha – 23BCE8158 \
Kundan Kumar Dubey – 23BCE8447
]
#pagebreak()

#front-heading([ABSTRACT])

CodeAI helps developers understand an unfamiliar codebase. CodeAI answers questions in chat. It creates quizzes based on a GitHub repository that is connected. Both of CodeAI's features first select the few files that a language model will look at. We ask what evidence should be used for each question: the words in a file, neural embeddings or the program's dependency graph. We tested nine file rankers, including CodeAI's original retriever, on 710 questions of three types (locate code, find direct importers, estimate change impact) across 19 JavaScript and Python repositories. Answer keys come from tools independent of our graph. Comments are removed before indexing. Five JavaScript repositories are held out. 18 comparisons, fixed after the held-out run, are Holm-corrected. For locating code, combining BM25, neural and graph rankings gives the highest held-out mean reciprocal rank (MRR 0.58 compared to 0.32 for BM25), though not significantly above the neural ranker alone. On importer questions, which mostly test parsing, the graph ranker reaches 0.97 compared to 0.68 for BM25; on change impact it leads BM25 (nDCG\@10 0.74 compared to 0.59), but not significantly. Adding the weak LSA ranker (weight 0.55) made our change-impact ranking of Python programs significantly worse: nDCG\@10 decreased by 0.11, although on held-out JavaScript the same fusion scored above the graph. As for the Graph Path Pruning method, it cut the number of returned dependency edges by 95%, partly by returning no edges for 8 of 25 questions; however, the results were lower than expected. Applied to 25 held-out flow questions, it obtained an F1 of 0.20, while a simple top-3 baseline gave 0.30 (the difference is not significant).

On the other hand, the retriever we rebuilt from these results performed better on CodeAI's held-out data. In particular, the MRR for locating code rose from 0.43 to 0.58, while that for importers increased from 0.68 to 0.97. Note that we chose this design after seeing the experimental results, so these improvements confirm the design rather than test it independently.

The benchmark also has 48 flow questions written by hand. On change impact, the highest held-out score we measured (nDCG\@10 0.91) came from fusing BM25 with the graph, a control that we added after the held-out run. For the same question type, the rebuilt retriever raised CodeAI's score from 0.58 to 0.78. Its gains over the original retriever remain when whole repositories are resampled. The analyzer behind the graph reproduces all 4,596 Python definitions and, after one post hoc fix of the resolver, finds 96.8% of the Python import links.

*Keywords:* repository-level code retrieval, empirical study, code graph, static analysis, dense retrieval, BM25, rank fusion.

*Code, data and scripts:* #link("https://github.com/Capstone-TEAM-VITAP/Capstone-VibeLearning")[`github.com/Capstone-TEAM-VITAP/Capstone-VibeLearning`]\; every number in this report is regenerated by those scripts.

#pagebreak()
#outline(title: [Contents], depth: 2, indent: auto)
#pagebreak()

= Introduction

CodeAI is a learning platform designed for developers who need to understand a codebase that they did not write themselves. A user connects a GitHub repository, which CodeAI's analysis service then transforms into a dependency graph. Users can ask questions via chat and take quizzes generated from the repository. Every answer is backed by references to the specific files from where the information was derived. These features work with the same process: first identifying a few files out of potentially hundreds to be read by an LLM, which then uses them to generate an appropriate answer. Since a model cannot cite or explain code it has not been given, this initial stage limits the quality of every answer and quiz question.

We focused on three kinds of questions learners ask: *where* is a feature implemented, *who* depends on this file, and *what* runs when a feature is used. Two families of evidence can answer them. Text-based rankers (keyword search or neural embeddings) read the contents of files, and structure-based rankers read the dependency graph that CodeAI's analyzer already builds. Recent research systems incorporate both and often make use of graph traversal techniques or graph-driven agents [18, 19, 20]; nonetheless, they rarely compare text against graph evidence for each kind of question.

This research measures that for CodeAI. The goal was to come up with a new technique for the product, which involves a hybrid retrieval process along with a graph pruning process. Our own measurements showed that neither of the two processes delivered what we expected; therefore, this report presents the study that those measurements support. Every candidate ranker, together with the retriever CodeAI’s chat and quizzes used before this study, is evaluated on the same questions, and the results guided an improved retriever that we built into CodeAI.

*Research questions.*
- *RQ1 (performance per question)*. What are the relative strengths of lexical, LSA, neural dense, and graph-based rankers at locating code, finding the direct importers, and estimating the change impact?
- *RQ2 (fusion)*. Is the performance of Reciprocal Rank Fusion of text and graph-based ranking better than the best individual ranker?
- *RQ3 (pruning)*. Does query-conditioned Graph Path Pruning recover the few dependency edges that carry a behaviour better than unpruned traversal and simple baselines?
- *RQ4 (validity of the instrument)*. How accurate is the static analysis used by the graph-based rankers for JavaScript and Python?
- *RQ5 (the product)*. How does the original CodeAI retriever perform compared to the above-mentioned rankers? How much does a retriever rebuilt from the findings improve it?

*Contributions.*
+ *A benchmark* involving 710 retrieval questions spread out over 19 repositories in two programming languages and also containing 48 flow questions, with retrieval answer keys extracted from tools independent of the system being tested and flow answer keys written by one author.
+ *A controlled comparison* experiment involving nine rankers, which includes CodeAI’s own production retriever, using held-out repositories, bootstrap confidence intervals, paired permutation tests, Holm correction over a family of 18 tests and a repository-level robustness check.
+ *Measured negative results* for rank fusion that involves adding a weak ranker and also for graph path pruning, which involved fair baselines, ablation study, and sensitivity analysis of all constants defined manually.
+ *An open instrument:* CodeAI analyzer (856 unit tests), validated against Python's `ast` module for definitions, imports and cross-file calls.
+ *A better product:* Chat/quiz retriever of CodeAI, re-built using the results (v2) and also assessed before and after on the same benchmark (@sec-implications).

= Related Work

*Language models and long contexts.* Code models [9, 10, 11, 12] work well within a file, but a repository exceeds any context window and long inputs are used unreliably [13], so a retriever must choose what the model sees.

*Retrieval for repositories.* Retrieval-augmented generation [3] finds text that is relevant to a query and passes it to the model. For repository-level completion, RepoCoder [4] alternates between retrieval and generation, while RepoBench [5] measures retrieval across files. CodeRAG-Bench [21] and CoIR [22] compare retrievers on code tasks, neural embedding models included. On the lexical side, BM25 [1] is still a strong baseline. Dense passage retrieval [14] and sentence embeddings [23] learn vector representations instead. The BGE family [24] offers small general-purpose embedding models, and we use one of them. LSA [6] is an older vector method that is not neural. RRF [2] is a standard way to merge ranked lists.

*Graphs and agents for repositories.* Programs have been represented as graphs for a long time, for example as program dependence graphs [17] and code property graphs [16]. CodePlan [15] uses a dependency graph to plan edits across a repository. RepoGraph [18] builds a graph of the repository at the level of lines and gives it to software-engineering agents, which are evaluated on SWE-bench [25]. In CodexGraph [19], an LLM agent queries a graph database that holds code symbols and their relations. LocAgent [20] turns a repository into a heterogeneous graph of files, classes and functions, and its agents walk through this graph to find the code that belongs to an issue. Agentless [26] uses no agents: it localizes first and repairs afterwards in a simple hierarchical pipeline, and it is competitive with agents.

*How this study differs.* All of these systems are judged on end-to-end task success with a language model in the loop, so retrieval quality and model behaviour are mixed together. We look only at the retrieval step. Different types of evidence are compared on the same questions, with answer keys that our graph did not produce, and we report where structure helps and where it does not. No language model is run in this study, so we make no claim about answer quality (@sec-limitations).

= Problem Formulation

The graph that is created by the CodeAI's analyzer consists of nodes and edges that represent files and symbols. A repository is a directed attributed graph $G = (V, E, tau_V, tau_E)$ where $V$ contains files, symbols (functions, classes, methods, variables) and architectural role nodes, and $tau_E$ gives each edge one of seven types (CONTAINS, IMPORTS, EXPORTS, CALLS, REFERENCES, DEPENDS_ON, CLASSIFIED_AS). In our research, all ranking algorithms work with the file-level projection, which is represented by $G_F = (F, E_F)$, where $(u, v) in E_F$ if file $u$ imports, calls into, or architecturally depends on file $v$. Of the symbol-level parts of $G$ we evaluate only definitions and cross-file CALLS edges (@sec-accuracy); the role classifier is used by one pruner component and is otherwise not evaluated.

For a given natural-language question $q$, the problem consists of the following subtasks:
- *Locate:* generate a ranked list $hat(F)_q$ favoring the file containing the implementation of the described behaviour, measured by MRR and Hit\@k.
- *Direct importers:* given a named file $x$, rank the files importing $x$, measured by MRR and Hit\@k.
- *Change impact:* given a named file $x$, rank the files dependent on $x$ in up to four import steps, measured by capped Recall\@10 and nDCG\@10.
- *Flow reconstruction:* return a small edge set $hat(E)_q subset.eq E_F$ where $|hat(E)_q| <= K_"max"$, matching the set of edges $E_q^*$ carrying the behaviour (edge F1).

= The Instrument: CodeAI

CodeAI has three layers (@fig-arch). The static analysis layer converts a repository snapshot into a graph. A retrieval layer ranks files and cuts edges. The chat and quiz features of CodeAI retrieve files using a JavaScript retriever, which is tested before and after rebuilding the retriever (@sec-implications).

#figure(image("figures/architecture.png", width: 80%), caption: [Architecture of CodeAI. The analysis service (blue) produces a graph. From a file-level view of this graph, the retrieval layer (green) builds four rankers and fuses them. The outputs (orange) are ranked files, flow edges, and CodeAI's chat and quizzes; the retriever of the chat and quizzes (v2) reuses the graph ranker and the fusion.]) <fig-arch>

== Parsing and Symbol Extraction

The files are parsed using Tree-sitter [8]. In *JavaScript/JSX*, the functions, classes, methods, variables, and constants declarations, as well as CommonJS/ES-module exports, are recognized as symbols; the imports, single-string `require`s, calls, and references are considered as relationships. In *Python*, `def`/`async def` (with or without decorators) are regarded as functions (or methods if they are defined directly inside classes); classes are modeled with tracked nesting; the module level assignments are considered as constants/variables; the imports (including `from … import`, relative imports, and star imports), and the calls are considered as relationships. Extraction is deterministic.

== Import and Call Resolution

*JavaScript:* Resolution for relative specifiers is achieved by appending them to the importing directory and trying to resolve them using common file extensions and indices; bare modules are considered external, and relative imports without a match are considered unresolved. *Python:* Dots at the beginning indicate going up directories; an absolute dotted name is tried against the root of the repository and each parent directory of the importing file, and then matched against the end of each Python file path (this was added after the first accuracy comparison was done; see @sec-accuracy). The function calls are connected to the symbol inside the file or imported by name.

== Graph Construction

The results are presented as a graph using stable ids (`file:<path>`, `symbol:<path>:<name>:<line>:<col>`) that are sorted in such a way that the graph generated by a particular repository remains the same all the time. Role classification is performed based on a set of rules where a file is marked as route, controller, service, and so on; but very few library repositories analyzed in this report have layers of roles.

== Rankers: Lexical, LSA, Neural Dense, Graph and Rank Fusion <sec-rankers>

- *CodeAI v1:* The JavaScript search engine that was used by CodeAI's chat and quiz generation prior to this study (`rankFiles` in `apps/backend/src/services/retrieval.service.js`). It computes BM25 scores for each file based on its content and path and also adds the score of 0.25 multiplied by the best overlap of words from the question with symbols in the file. The same production code is used without modifications in Node.js.
- *BM25* ($k_1 = 1.2$, $b = 0.75$) on identifier-aware tokens of file contents and file names (camelCase and snake_case separated).
- *LSA vectors:* TF-IDF, followed by truncated SVD (64 dimensions). This is not a neural model. However, we still use it because it was the "semantic" ranker in our original design.
- *Neural dense:* the pretrained sentence-embedding model `BAAI/bge-small-en-v1.5` [24] (33M parameters, CPU). The file is broken down into windows of 40 non-empty lines with its path as prefix; the score for a file is the best cosine similarity of its windows; queries use the retrieval prefix of the model. Embedding all 19 repositories in both text conditions and answering all questions took 14 minutes on CPU of a laptop.
- *Graph ranking:* If the query contains a file name and uses any dependency word (import, depend, affect, impact, break, use), then the order of files will be based on the reverse-import distance to the named file, up to a distance of four at the most. In all other instances, the order will be determined by the number of query words contained in the paths and symbol names of the files, giving half credit to the direct neighbors of matches. It needs to be pointed out that the graph ranking algorithm does not examine the files' content; for questions without a named file it relies on names, and the dependency graph enters only through the neighbour credit.
- *Fusions* use RRF, $"Score"(d) = sum_m w_m / (k_0 + r_m (d))$ with $k_0 = 60$: *RRF LSA + graph* ($w = 0.55, 0.45$; the fusion of our original design), *RRF dense + graph* (same weights), *RRF BM25 + dense + graph* (equal weights) and *RRF BM25 + graph* (equal weights). This final component was added after the held-out run; its function is as a control that combines the graph with a weak but non-trivial text ranker. It is presented purely descriptively and does not belong to the test family.

The values of the LSA weights and $k_0$ were set before any evaluation was conducted; this will be covered in @sec-fusion.

== Graph Path Pruning

In the case of flow-based problems, the pruner assigns a score to each of the non-test file edges of the problem and then keeps only a small, connected sequence of edges (Algorithm 1, @fig-pruning). The relevance of a file is calculated based either on the percentage of question terms appearing in the path (path version) or on its reciprocal rank in a search ranking (BM25 version, our main and fusion version).

#figure(image("figures/pruning_flow.png", width: 100%), caption: [Graph Path Pruning in four steps. We set all constants by hand before the held-out run; @tab-sens reports how sensitive the results are to each one.]) <fig-pruning>

#block(width: 100%, above: 0.6em, inset: (x: 8pt, y: 5pt), stroke: 0.6pt + luma(160), radius: 2pt, breakable: false)[
  #text(weight: "bold")[Algorithm 1: Query-conditioned Graph Path Pruning]
  #v(2pt)
  #show raw.where(block: true): set text(size: 7pt)
```text
Input : file graph G = (F, E), question q, K_max (default 3), relevance map rel, threshold T (default 2.0)
Output: at most K_max edges
1:  E' <- edges (u, v) in E where neither u nor v is a test file
2:  [layer rules] primary/secondary <- controllers reached from a relevant route / relevant themselves
3:  C <- []
4:  for each edge e = (u, v) in E':
5:      base <- 1.5 * rel(u) + 1.5 * rel(v);  if base = 0 then continue
6:      s <- base + max over kinds of e of {depends_on: 2.0, calls: 1.5, imports: 0.5}
7:      [layer rules] if e goes one layer down (route > controller > service > repository/model):
8:          s <- s + 3.0, plus 5.0 / 4.5 / 2.5 for the route->controller and controller->service cases
9:      if s >= T then C.append((s, e))
10: S <- []
11: while C is not empty and |S| < K_max:
12:     pick the edge with the highest score, +2.0 if it connects to an edge in S (ties: alphabetical)
13:     skip it if its reverse is already in S; otherwise append it to S
14: return S
```
]

Layer-specific rules (lines 2, 7, and 8) can be applied only to the edges between the files that belong to the adjacent layers of a web application according to the role classifier. As demonstrated in @sec-pruning, there is not a single edge in the held out flows satisfying the requirements, making those lines inert on the held-out flows.

= Experimental Design

== Repositories and Splits

#plain-table(
  (1.3fr, 3.2fr, 2.4fr),
  ([*Split*], [*Repositories*], [*Role in the study*]),
  [JS development (3)], [`hackathon-starter`, `koa`, `react-redux-realworld-example-app`], [Used during the design of the rankers and pruner.],
  [JS post-hoc test (7)], [`express`, `hapi`, `axios`, `react-boilerplate`, `node-fetch`, `passport`, `connect`], [Considered before the final design and reported together with development as "post-hoc JS (10)."],
  [JS held-out (5)], [`request`, `winston`, `mocha`, `redux-saga`, `body-parser`], [Not used in any design decisions (*confirmatory*).],
  [Python (4)], [`requests`, `click`, `flask`, `httpx`], [Added when we extended the study to a second language; considered the second test set, not confirmatory.],
)

The Python repositories were not used in the ranker design; nonetheless, they are not blind either -- the Python import resolver was corrected based on its accuracy on them (@sec-accuracy), and they account for 21 out of the 25 held-out flow questions. Python retrieval outcomes are therefore considered the second test set, not confirmatory. Commits are pinned in `research/repos.json`. Repositories were chosen by the authors and not randomly sampled, and are largely composed of libraries, not layered web applications.

== Retrieval Questions <sec-questions>

Answer keys come from oracles that do not use our Tree-sitter graph (@tab-questions).

#tbl(
  [The three types of retrieval questions, each with an example, the way its answer key is built and the number of questions per group.],
)[#plain-table(
  (1.15fr, 2.5fr, 2.4fr, 1.6fr),
  ([*Question type*], [*Example*], [*Answer key*], [*Questions (held-out JS / post-hoc JS / Python)*]),
  [Locate],
  ["Convert a data object to FormData" (the first sentence of a JSDoc comment or docstring, with the function name absent)],
  [The file containing that comment. Duplicated sentences are dropped.],
  [79 / 144 / 120],
  [Direct importers],
  ["Which files import lib/request.js?"],
  [Files that import it: regular expressions over comment-free source (JS), `ast` (Python).],
  [48 / 85 / 59],
  [Change impact],
  ["Which files are affected if lib/utils.js changes?"],
  [Files depending on it through up to four import steps (3 to 30 files, tests excluded).],
  [37 / 78 / 60],
)] <tab-questions>

*Comment removal.* Locate questions are formed from comments; thus, in accordance with standard practices for comment-derived code search queries [27], all `//` and `/* */` comments are removed by means of lightweight lexer taking strings, template literals, and regular expression literals into account. Moreover, all Python `#` comments and docstrings are removed prior to the text indexing performed by any ranker. Then normalization which includes case and punctuation standardization confirms that there is no text of question in the corresponding answer file. Thus, #n-dropped question was detected, the text of whose "sentence" consisted only of the piece of code; this question was excluded, resulting in 343 location questions and 710 questions altogether. There was an evaluation version which indexed comments; #link(<app-comments>)[the appendix dedicated to comment indexing] describes how this change affects the results.

Importer and impact questions name a file and ask about importing dependencies. Answer keys to such questions are built on the same relationship as the graph ranker (although computed by different tools). Therefore, the graph ranker is a kind of lookup in these two cases, where the score mainly shows parsing precision. We include such questions into reports to verify whether the retriever uses structural information where appropriate. The high graph score for these questions does not give us much information on the ranker's architecture.

== Flow Questions

The questions in the flow category determine the file-to-file edges that represent a certain behavior (for instance, "How are user sessions stored in signed cookies?") and have two or three edges that correctly answer the question, and all those edges are independently verified as existing by the import oracle. A development set that contained 23 questions (related to the backend and `hackathon-starter` of this project) was used for the purposes of conducting an error analysis when designing the pruner. A test set containing 25 questions (21 of which came from the four Python projects, while the other 4 were from `koa`, `express`, and `hapi`) was created before running any of the content-based pruners on the data. One of us wrote both the questions and the pruner; no second annotator checked them.

== Methods Compared

*Retrieval:* a seeded random ranking (floor), CodeAI v1, along with eight rankers introduced in @sec-rankers. CodeAI v2, an improvement based on these findings, will be presented in @sec-implications.

*Flows:* a stochastic 3-edge floor; three unpruned baselines (2-hop traversal using the top 3 path matching files, 2-hop traversal using the top 3 BM25 files, and candidate pool of the pruner, i.e., all edges whose endpoint file is a top-10 BM25 file); two simple top-3 baselines (path words and BM25 based); the pruner using path, BM25 (primary), and fusion relevance; and ablation versions thereof. The 2-hop traversal based on our previous report uses seeds which differ from that of the pruner; the latter two give an unpruned baseline which have the same evidential basis as the pruner.

== Metrics

Hit\@1 is the ratio of questions that have the first result correct. MRR is the mean of reciprocal of the rank of the first correct file with zero value when there is no correct file within the cutoff. nDCG\@10 gives more credit to correct files located close to the top of the ranking and is normalized by the best order.

In the case of impact assessment, we use cRecall\@10, defined as the ratio of the correct files among the top 10 divided by $min(|I_q^*|, 10)$. Plain Recall\@10 is upper bounded by $10 \/ |I_q^*|$ and 66 out of 175 impact-related questions have more than 10 affected files.

Edge precision, edge recall and F1 score are reported for flow-based metrics. For the locate and importer metrics, we use a cutoff of $K = 7$, equal to the number of files our chat sends to the model, so MRR in the tables is MRR\@7. As seen from Appendix B.2, the ranking of methods does not change at $K = 10$ and formal definitions and commands for reproduction of all the results are provided in Appendices A and D.

== Statistics

The intervals are 95% bootstrap percentile intervals [7] based on questions (2,000 resamples for retrieval tables, 5,000 for flows and differences). The paired differences are analyzed with a sign-flip permutation test (exact for 18 or fewer nonzero differences; otherwise, 20,000 seeded draws). A p-value is the probability, assuming the null hypothesis of equal performance between the two methods, of observing an average absolute difference at least as large as observed (two-tailed). Seeded draws are used both for bootstraps and permutations and are defined in `research/py/common.py`. Due to the multiple tests performed, one family of 18 paired tests was fixed (see @tab-sig) after the holdout experiment but before manuscript writing, and family-wise error rates are controlled by applying Holm–Bonferroni procedure [28]. The family was therefore not pre-registered, and the correction does not account for the choice of comparisons. Differences are considered significant if the p-value adjusted by Holm-Bonferroni correction is smaller than 0.05. Tests labeled as *post hoc* are selected based on the held out results and are exploratory.

*Questions are not independent:* questions from the same repository have the same code style, naming conventions, and graph structure, and the held out locate questions are imbalanced (30, 30, 12, 6, and 1 question per repository). Therefore, the intervals and tests performed across questions can exaggerate evidence regarding general statements about repositories. For each key comparison, we additionally report, across repositories, the number of repositories where the average score favors each method and the 95% interval based on resampling repositories (@tab-repo). As there are five repositories, a sign test cannot achieve $p < 0.05$ (the lowest two-tailed p value is 0.0625); therefore, the repository level results serve as a directional and consistency test, but not a secondary test for significance.

= Results <sec-results>

#tbl([Main findings, on held-out JavaScript unless another group is named. "Holm" means that the difference remains after correction for 18 tests.])[
  #plain-table(
    (1.6fr, 1.7fr, 2.7fr, 2.6fr),
    ([*Question*], [*Best evidence*], [*Result*], [*Limit of the result*]),
    [Where is it implemented?], [Learned text meaning together with names (fusion)], [The neural dense ranker is +0.18 MRR above BM25 (Holm). The fusion of BM25, dense and graph reaches 0.58.], [The gain of fusion over dense alone (+0.08) was not tested. The neural ranker leads BM25 in 3 of 5 held-out repositories and in all 4 Python repositories.],
    [Who imports file X?], [Graph], [MRR of 0.97 for the graph and 0.68 for BM25 (Holm)], [Almost a lookup, because the answer key and the graph use the same import relation.],
    [What is affected if X changes?], [Fusion of graph and text (descriptive)], [nDCG\@10 of 0.74 for the graph, 0.59 for BM25 and 0.91 for BM25 + graph (post hoc)], [On held-out JS no impact comparison remains after Holm. On Python, adding LSA *lowers* the score (−0.11, Holm over questions but not over repositories).],
    [Which edges form a flow?], [No reliable winner], [F1 of 0.20 for the primary pruner and 0.30 for the top 3 by path words], [Only 25 questions, and no flow comparison remains after Holm.],
    [Did it improve CodeAI?], [CodeAI v2], [Held-out scores rise from 0.43 to 0.58 (locate), from 0.68 to 0.97 (importers) and from 0.58 to 0.78 (impact). v1 was significantly below the strongest declared ranker for every type.], [We chose the design after seeing results, so this confirms it and is not an unbiased test. The gains hold when repositories are resampled.],
    [Is the instrument accurate?], [Yes, for the parts we checked], [It finds 100% of 4,596 Python definitions, 96.8% of imports (after one post hoc fix) and 96.4% of direct cross-file calls.], [The role classifier and JS calls were not checked.],
  )
]

== Retrieval Across Question Types (RQ1)

#tbl([Retrieval results on the five held-out JavaScript repositories with comments removed. The best value in each column is in bold green. #super[c]Recall\@10 is capped, which means that it is divided by $min(|"answer"|, 10)$.])[
  #retrieval-heldout
] <tab-heldout>

#tbl([The same rankers on the 10 development and post-hoc JavaScript repositories and on the four Python repositories, again with comments removed.])[
  #retrieval-other
] <tab-other>

#figure(image("figures/retrieval_js.png", width: 100%), caption: [Results on held-out JavaScript with comments removed (mean and 95% bootstrap interval). Text meaning and names help for locate questions, and the graph dominates importer questions. For change impact, the fusions that include the graph score highest, but no impact comparison survives correction.]) <fig-retrieval-js>

#figure(image("figures/retrieval_py.png", width: 100%), caption: [Results on Python with comments removed. They follow the pattern of JavaScript with one exception: for change impact, the LSA-graph fusion is below the graph alone and the dense-graph fusion is above it.])

*Locate.* Neural and structural signals perform better than keywords (@tab-heldout, @fig-retrieval-js). The neural dense ranker beats BM25 on JavaScript questions held-out (+0.178 MRR, Holm p = 0.015) and Python (+0.191, Holm p = 0.0009) questions, and outperforms LSA (+0.251). Fusion of BM25, dense, and graph ranking is the best research ranker in all three groups (0.58, 0.69, 0.61), and beats BM25 by +0.260 on held-out JavaScript (Holm p = 0.0009). The difference from dense alone (+0.08 on held-out) is descriptive. For each of the repositories (@tab-repo), fusion beats BM25 on all held-out repositories with one exception, while the neural ranker beats BM25 on all Python repositories. The neural advantage on held-out JavaScript is less general: it is observed on three repositories with 72 out of 79 locate questions, while it is reversed in `body-parser` (6 questions) and `request` (1 question), the difference between the two having an interval which contains zero. The original CodeAI retriever (v1, 0.43) is better than plain BM25, presumably because of the symbol-name bonus, but still falls behind both the neural ranker and fusion.

*Direct importers.* The graph ranker achieves near perfection (0.97 held-out, 1.00 on the other two groups) and beats BM25 by +0.294 (Holm p = 0.0009). Fusion decreases this gap (RRF LSA + graph minus graph = −0.100; not significant after correction) since text rankers boost non-importers. As pointed out in @sec-questions, this result confirms the correctness of the import graph.

*Change impact.* Graph-based rankings beat text-only rankings (held-out nDCG\@10: 0.74 for the graph, 0.59 for BM25, and 0.27 for dense), although the small size of the held-out dataset (37 questions) is not enough for the difference to be significant (raw p = 0.083, Holm p = 0.67). Graphs beat BM25 on four held-out repositories but lag behind on `redux-saga` (15 questions). Neural embeddings have little value here since the files depending on `utils.js` are not required to be similar to it.

#tbl([Locate MRR for different shares of question words that occur in the comment-free answer file (all 343 locate questions, split into thirds). BM25 needs shared words. The dense and graph rankers lose less when few words are shared, and fusion is the best at every level.])[
  #overlap-table
] <tab-overlap>

*Why BM25 loses.* @tab-overlap demonstrates locate question classification based on lexical similarity. While BM25 has an MRR of 0.16 where only a small set of words from the question is present in the file, dense (0.38), graph (0.41), and fusion ranking (0.50) models retain their ability to find the file. However, under the scenario of a high lexical similarity, BM25 reaches the performance of dense representation model (both have MRR of 0.58), but the fusion technique still performs better than others (0.77). This means that the combination of the name (identifier and path) with learned semantics is valuable at every overlap level we measured.

== Rank Fusion (RQ2) <sec-fusion>

For locating code, fusing all three rankers is the most effective approach in each group. The effectiveness of fusion depends on the efficiency of each member concerning the particular question type since the presence of an ineffective member that has a high weight can damage the performance:
- For importers, no fusion under consideration beats the graph ranker in isolation (BM25 + graph only ties it), as text rankers add noise due to their approximation to the exact answer.
- For Python change impact, the fusion of the graph with the weak LSA ranker (at the pre-set weight 0.55) provides significantly worse performance than the graph alone over questions (−0.107 nDCG\@10, Holm p = 0.0009). On the contrary, fusion with the neural ranker improves the performance (0.84 versus 0.78; not in the test family).
- The LSA loss is observed in three out of four Python repositories (@tab-repo).
- The BM25 + graph control makes the distinction between "fusion with a weak member" and "LSA is weak." BM25 alone has a much lower impact score than the graph (0.59 versus 0.74 on held-out data); nevertheless, the combination of these techniques leads to the highest observed impact score on the held-out data (0.91 versus 0.74 for the graph alone). The impact score is close to the graph everywhere else (0.89 versus 0.91 post-hoc JS, 0.79 versus 0.78 for Python), agrees with the graph on held-out importers (0.97) and provides 0.55 locate MRR without a neural model. These comparisons are post hoc and untested. The comparison between these techniques suggests that the observed loss is due to LSA itself rather than the fusion process.
- Analysis of the variations (Appendix B.1) of the LSA weight (0.2 to 0.8) and $k_0$ (10, 60, 200) on the held-out dataset shows that the pre-set LSA weight (0.55) was in the upper half of the values tried: when $k_0 = 60$, the reduction of this value to 0.2 increases the locate MRR from 0.380 to 0.411, importer MRR from 0.873 to 0.955 and impact nDCG\@10 from 0.831 to 0.856. The effect is not monotone for locate (0.5 gives 0.367, below 0.55), but for every type the lowest LSA weights (0.2 or 0.35) score highest. Retuning was not performed, since this sweep uses held-out data.

== Graph Path Pruning (RQ3) <sec-pruning>

#tbl([Flow reconstruction on the 25 held-out flows. "Empty outputs" counts the questions for which no edges were returned. Precision, recall and F1 are averages over questions.])[
  #flows-held-out
] <tab-flows>

#figure(image("figures/flows.png", width: 100%), caption: [Flow reconstruction on the held-out questions. Left: F1 with its 95% bootstrap interval (hatched bars are post hoc). Right: edges returned per question. Although the primary pruner removes about 95% of the candidate edges, it does not beat the simple top-3 baselines.]) <fig-flows>

*Against fair unpruned baselines.* The pool of edges that the pruner considers (@tab-flows, @fig-flows) consists of 86% of the true edges, yet it produces 36.9 edges per question (F1 = 0.146). The primary pruner, which considers the relevance of edges from BM25, keeps only 1.9 edges out of the pool (95% pruned) and reaches F1 = 0.200, which is +0.054 more, which is not statistically significant (p = 0.46). Traversal starting from the same seeds of BM25 is weaker than the pool (F1 = 0.064, 33.3 edges), so the pruner wins +0.136 over traversal (raw p = 0.052, corrected p = 0.47).

*Against simple baselines.* The primary pruner is inferior to "top 3 edges by path words" and "top 3 by BM25" baselines, losing −0.100 and −0.056, correspondingly. Though neither of those losses is statistically significant, both suggest an inclination against pruning.

*Empty outputs.* The primary pruner has produced zero edges for 8 out of 25 questions of the held-out set. As the reciprocal rank relevance is not greater than 1 (and usually much smaller), then, in most cases, $1.5 times (r_u + r_v)$ + import bonus of 0.5 is less than the fixed threshold 2.0. When the threshold is lowered to 0 (post hoc change), 7 out of 8 empty outputs are eliminated and F1 becomes 0.285, which is still not significantly better than the "top 3 by BM25" baseline (gain +0.029, p = 0.63). The variant with fused relevance (F1 = 0.353, post hoc) is the best-flow algorithm examined; still, it wins over top 3 by BM25 by +0.097 (raw p = 0.031) only, while this advantage disappears after the Holm correction (p = 0.34).

*Layer rules.* The strongest evidence is provided by the development set, when layer rules are applicable. They are triggered in 19 of 23 questions (203 of 701 edges); their exclusion raises F1 from 0.267 to 0.290. In the held-out set, layer rules are never triggered (none of 923 candidate edges, 0 of 25 questions are in adjacent layers), so held-out questions test only the layer-free part of Algorithm 1, so "no layer rules" ablation is the same as the full pruner. Exclusion of the continuity bonus also increases the F1 score of the held-out set (0.264 vs. 0.200).

#tbl([Mean F1 of the primary pruner when each hand-set constant is halved or doubled, one at a time. The held-out score changes only with the threshold, the relevance weight and the edge-kind weights, and the reason is the problem of empty outputs: a doubled threshold leaves every held-out answer empty.])[
  #pruner-sensitivity
] <tab-sens>

*Constants.* Each of four layer constants and continuity bonus of Algorithm 1 were independently increased/decreased twice (doubled/halved; see @tab-sens). The layer constants and continuity bonus do not affect the held-out score (0.200); relevance and edge kind weights can move the score in the range 0.171 -- 0.227. Threshold affects the score the most -- the score becomes 0.243 when it is halved and 0.000 when it is doubled. None of those changes help the pruner to beat the baselines.

== Instrument Accuracy (RQ4) <sec-accuracy>

#tbl([Agreement of the analyzer with independent reference tools. "Found" is the share of the reference items that the analyzer also reports, and "correct when reported" is the share of its output that the reference confirms. #super[s]For calls, precision is measured only on those edges of the analyzer that lie inside the scope of the oracle, which is a name imported with `from m import name` and called directly.])[
  #accuracy
]

#figure(image("figures/accuracy.png", width: 100%), caption: [Recall of import edges for each repository, measured against the independent oracles. The vertical axis starts at 0.85.])

Definition checking is the least demanding test of the four because there is substantial agreement between the two Python parsers about the positions of the `def` and `class` statements. However, import and call checks analyze resolution, where static analyzers often fall short. The import recall scores for `requests`, `click`, `flask`, and `httpx` repositories are 0.922, 0.983, 0.963, and 1.000, respectively. The original Python resolver had 0.637 recall of import links due to skipped package imports from another source tree (such as `src/click` imported from `examples/`). After comparing the results, suffix matching was introduced, which raised recall to 0.968. For the first time cross-file call edges were investigated here, recovering 96.4% of 357 call edges from the imported functions and classes with no false edges found in that set. The call via module attributes (`m.f()`), JavaScript calls, and the role classifier have not been verified yet. The left-over JavaScript import misses mostly occur for `export … from` re-exports which are shown as exports in the graph.

== Robustness Across Repositories

#tbl([Key differences across questions and across repositories (comments removed). "Repositories where A > B" category compares mean per repository. Repository interval is calculated based on resampling the whole repository (5,000 draws). Green bold text signifies an interval which does not contain zero. When we have four or five repositories, these intervals are usually large and unstable; they point towards the direction but not statistical significance.])[
  #repo-table
] <tab-repo>

The following results remain at the repository level: (1) three-way fusion outperforms BM25 for locate, (2) the graph outperforms BM25 for importers in all five repositories, and (3) the neural ranker outperforms BM25 for Python in all four repositories. CodeAI v2 improvements over CodeAI v1 remain. The following results are not robust: (1) the neural ranker holds an edge over BM25 (and LSA) only based on three largest held-out repositories, and (2) the LSA-fusion loss against the graph on Python appears in three out of four repositories, with zero included in the interval.

== Statistical Significance

#tbl([The family of 18 paired tests, which we fixed after the held-out run (comments removed; held-out JS unless marked Python; flows on the 25 held-out questions). Each difference is A minus B, averaged over questions. A Holm-adjusted p < 0.05 is shown in bold green. The rows marked post hoc were not planned; they are in the table so that the correction covers them as well.])[
  #significance-table
] <tab-sig>

Of the eighteen tests conducted, six of them survive multiple testing corrections. All these comparisons relate to retrieval efficiency: dense representations are better than BM25 and are also better than LSA in locate retrieval; tri-fusion is better than BM25 in locate retrieval; graph-based techniques are better than BM25 in importers; and LSA-graph fusion is worse than graph-based techniques in Python impact. No comparison related to flow survives multiple testing corrections; two of which even had raw p-values less than 0.05.

== Answers to the Research Questions

- *RQ1.* Regarding importer-related questions, which are focused on evaluating parsing abilities, the graph demonstrates nearly perfect performance and significantly outperforms any text-based rankers. As for change impact evaluation, the graph is winning but not significantly. Signals important for locate task include learned semantics with the help of neural embeddings and naming information (more specifically, the path and symbol matching used by the graph ranker). Other than LSA, plain keyword search is the worst non-random ranker.
- *RQ2.* Fusion of BM25, neural, and graph rankings gives the highest locate score achieved by us. Combining the graph with high-weight LSA can be sometimes worse than the graph itself, while fusion with BM25 always stays within 0.02 of the graph or beats it, which shows that the primary danger lies in the weak component, and not in the fusion process itself. No fusion configuration outperforms the graph on importer questions.
- *RQ3.* Graph Path Pruning reduces the set of results by 95% in comparison to the candidate set size. As specified by the predefined formulation, it fails to beat the top-3 baselines, with its layer rules inactive on held-out questions, and no flow comparison staying significant after correction.
- *RQ4.* Analyzer perfectly reproduces Python definitions and successfully resolves 96.8% of Python imports (measured on the four repositories used to correct the resolver), 98.5% of JavaScript imports and 96.4% of direct Python cross-file calls.
- *RQ5.* The original CodeAI retriever (v1) was significantly weaker than the strongest declared ranker across all question types (see @tab-v1, post hoc). Our rebuilt retriever (using graph routing on importer questions, and text, graph and neural fusion otherwise) reaches the performance of the strongest ranker on locate and importer questions (held-out MRR 0.43 to 0.58 and 0.68 to 0.97 respectively), but not on change impact (nDCG\@10 = 0.78, while 0.91 for the control condition -- BM25 + graph; see @sec-implications).

= From Research to Product: CodeAI v2 (RQ5) <sec-implications>

The chat and quizzes' generation of CodeAI rely on a single retrieval function and thus have the retrieval quality and system quality coincide from the user's perspective. Before this study, the retrieval function (*v1*) used BM25 supplemented with symbol name bonus. With v1, on the held-out JavaScript data, the MRR was 0.43 vs 0.32 for the bare BM25, which means that the function helped CodeAI find code. However, for import and impact-type questions, there was no such effect as the method did not use the dependency graph created by CodeAI's own analyzer.

*What was changed.* The retriever (*v2*) was developed according to the results described in @sec-results:
+ *Importer questions:* The graph is used. Questions, where a particular file is mentioned and its importers, dependencies, or usage are asked, are answered using the reverse dependency ranking by the graph ranker.
+ *Other questions:* Fusion is used. Change-impact and general questions are answered using Reciprocal Rank Fusion (RRF) of the v1 text ranking, the graph ranking, and the neural embedding ranking if available.
+ *Neural ranking:* Optional. The AI service creates an embedding of a snapshot in the background during the first question regarding the item in the snapshot and answers subsequent questions based on that index. If the neural model is not available, if the index is unavailable or if the execution exceeds 2.5 seconds, v2 ranks without neural ranking.
+ *Excluded components:* Latent Semantic Analysis (LSA) and Graph Path Pruning were not used since none of them provided any improvement in @sec-results.

*Implementation details.* The graph ranker and RRF were implemented in JavaScript (`apps/backend/src/services/graph-retrieval.service.js`). The neural ranker is one of the implementations (`apps/ai-service/src/retrieval/dense.py`) and is common for both the product and this study's experiments. The production code, without changes, was tested on the same question sets.

#tbl([CodeAI's retriever before (v1) and after (v2) this study with comments removed, next to the best research ranker for each question type. "v2, no embeddings" stands for v2 without the optional neural model. The best CodeAI version in each row is in bold green.])[
  #product-before-after
] <tab-product-ba>

#tbl([CodeAI v1 compared with the strongest ranker of the declared comparisons for each question type on held-out JavaScript. These three tests were added after the study and have their own Holm family.])[
  #v1-tests
] <tab-v1>

#tbl([CodeAI v2 (deployed) compared with v1 on held-out JavaScript. We chose the v2 design after seeing the results of @sec-results on these repositories, so the table confirms the chosen design and cannot be read as an unbiased test. The Holm correction is applied within these three tests.])[
  #product-tests
] <tab-product>

*Results.* On the held-out JavaScript data, v2 improves the MRR for locating code from 0.43 to 0.58 and for importer identification from 0.68 to 0.97 and increases nDCG\@10 for change impact from 0.58 to 0.78 (see @tab-product-ba). All three improvements are statistically significant (@tab-product). In terms of locating and importer categories, v2 equals the best research-based ranker among all groups. As far as the change impact category goes, however, it does not beat the baseline of BM25 + graph with nDCG\@10 equal to 0.91 on the held-out repositories compared to 0.78 for v2. Thus, redirecting impact questions to that fusion is suggested. No modification was applied to v2, because any alternative would again be chosen on the same evidence. Before the upgrade, v1 lagged behind the strongest stated ranker for all types of questions (@tab-v1). These three tests were introduced after the experiment and form an independent Holm family. The improvements of v2 over v1 also hold at the repository level: none of the intervals over repositories contains zero (@tab-repo). There is one discrepancy with respect to the design of v2. For JavaScript change impact questions, adding the neural ranking led to the decrease in nDCG\@10 score from 0.83 to 0.78 on the held out set (0.90 to 0.82 on post-hoc JS); for Python, it increased the score from 0.80 to 0.83. The design stayed as stated rather than fine-tuned on the same data.

*Caveat.* These are retrieval scores. Whether v2 provides better chat answers, better quiz questions, faster learning will have to be assessed through evaluation of the outputs of the language model and of the learners (@sec-limitations).

= Threats to Validity

*Construct validity.* Locate questions work as comment sentences to describe behavior according to the author's terminology and can still favor text rankers against open-ended developer questions. The importer and impact answer keys have the same import relationship with the graph ranker. Flow answers represent the judgment of an individual, generated by the designer of the pruner. The importer and impact question templates also contain the dependency words that switch the graph ranker to reverse-import ranking (@sec-rankers), so those scores assume routing that never fails; paraphrased questions were not tested.

*Internal validity.* There were several design decisions made based on the results analysis: Python suffix matching resolver, content-based pruner (error analysis on development set), fused relevance and threshold-0 pruner variations (held-out run), and this study framing. Comment deletion was included after the previous version of the evaluation using comments indexing (see #link(<app-comments>)[the appendix on indexing comments]); this change led to conclusions contrary to our initial approach rather than supporting it. CodeAI v2 was created after the held-out results; thus, the measured prior-to-post improvement confirms the chosen design rather than tests the design on unseen repositories. Our prior report Python retrieval figures were not reproducible from the committed graphs; all figures presented here are regenerated from the scripts at the mentioned commits.

*External validity.* Nineteen repositories were chosen by the authors, mainly JavaScript and Python libraries, each containing up to a few hundred files. We use a single small general purpose embedding model; therefore, the conclusions about the neural rankers relate to this model, and large code-specific models can increase the dense ranker's advantage or improve the ranker's performance on change impact.

*Statistical validity.* There were small number of held-out samples (37 to 79 retrieval questions per type, 25 flows) from only five repositories, so the tests performed over questions assume independence of correlated questions. @tab-repo shows the repository-level picture where there is no held-out advantage of the neural ranker over BM25 anymore. Holm correction prevents false positives but decreases statistical power, so "not significant" sometimes means not enough data rather than the absence of the effect.

= Limitations and Future Work <sec-limitations>

We test for retrieval effectiveness and not for the correctness of the final answer: in the next stage, we evaluate a language model fed with the top-$k$ documents from each ranker and test their answers and citations. Locate questions should be written by developers that have not seen the source code, while a second annotator should control the increased set of flows, that covers layered web applications. We tested one small general purpose embedding model; future evaluations include comparison with an embedding model that has been trained with the source code and agentic graph exploration techniques like LocAgent [20]. The role classifier, JavaScript calls resolving, and Python attribute calls are not confirmed yet. We should normalize relevancy for pruning and test a fused relevancy version on new question flows.

= Conclusion

The goal of our work is to improve the ability of CodeAI to localize code that forms the base of its chat answers and quizzes. According to our evaluations, the dependency graph is the most reliable feature for importer identification (the task that is very similar to graph lookup), leads for change impact estimation, though not significantly, and allows localizing code using file and function identifiers. For code localization, a small neural embedding model is more accurate than keyword matching (+0.18 MRR for JavaScript and +0.19 for Python; across repositories, in all four Python repositories but only three of five held-out JavaScript ones). Fusion of this model with BM25 and dependency graph gives the best locate performance. Fusion degrades when one of the components is weak for the question type, e.g., Latent Semantic Analysis (LSA), or any text ranker on importer questions. On the other hand, fusion of the graph with BM25 provides the best held-out ranking for change impact (a post hoc control, not tested for significance).

Our predesigned graph pruning technique did not give better results than simple baselines. Therefore, the retriever of CodeAI was redesigned as Version 2: importer questions are handled by the dependency graph, and textual, graph-based and neural rankings are fused for the rest of the queries. As a result, there is an improvement in code localization (from 0.43 to 0.58 MRR), importer identification (from 0.68 to 0.97), and change impact ranking (from 0.58 to 0.78 nDCG\@10) on held-out repositories; since v2 was designed after seeing these results, this confirms the design rather than testing it. The benchmark, the analyzer, and all negative results are publicly available at #link("https://github.com/Capstone-TEAM-VITAP/Capstone-VibeLearning")[`github.com/Capstone-TEAM-VITAP/Capstone-VibeLearning`].

#heading(numbering: none)[References]

+ S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 and beyond," _Foundations and Trends in Information Retrieval_, vol. 3, no. 4, pp. 333–389, 2009.
+ G. V. Cormack, C. L. A. Clarke and S. Büttcher, "Reciprocal rank fusion outperforms Condorcet and individual rank learning methods," in _Proc. 32nd ACM SIGIR_, pp. 758–759, 2009.
+ P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W.-t. Yih, T. Rocktäschel, S. Riedel and D. Kiela, "Retrieval-augmented generation for knowledge-intensive NLP tasks," in _Advances in Neural Information Processing Systems 33_, 2020.
+ F. Zhang, B. Chen, Y. Zhang, J. Keung, J. Liu, D. Zan, Y. Mao, J.-G. Lou and W. Chen, "RepoCoder: Repository-level code completion through iterative retrieval and generation," in _Proc. EMNLP_, pp. 2471–2484, 2023.
+ T. Liu, C. Xu and J. McAuley, "RepoBench: Benchmarking repository-level code auto-completion systems," in _Proc. ICLR_, 2024.
+ S. Deerwester, S. T. Dumais, G. W. Furnas, T. K. Landauer and R. Harshman, "Indexing by latent semantic analysis," _Journal of the American Society for Information Science_, vol. 41, no. 6, pp. 391–407, 1990.
+ B. Efron and R. J. Tibshirani, _An Introduction to the Bootstrap_. Chapman and Hall/CRC, 1994.
+ Tree-sitter, an incremental parsing system for programming tools, https://tree-sitter.github.io/tree-sitter/ (accessed Nov. 2026).
+ B. Rozière, J. Gehring, F. Gloeckle, S. Sootla, I. Gat, X. E. Tan, Y. Adi, J. Liu, R. Sauvestre, T. Remez, J. Rapin, A. Kozhevnikov, I. Evtimov, J. Bitton, M. Bhatt, C. Canton Ferrer, A. Grattafiori, W. Xiong, A. Défossez, J. Copet, F. Azhar, H. Touvron, L. Martin, N. Usunier, T. Scialom and G. Synnaeve, "Code Llama: Open foundation models for code," arXiv:2308.12950, 2023.
+ R. Li, L. Ben Allal, Y. Zi, N. Muennighoff, D. Kocetkov, C. Mou, M. Marone, C. Akiki, J. Li, J. Chim, Q. Liu, E. Zheltonozhskii, T. Y. Zhuo, T. Wang, O. Dehaene, M. Davaadorj, J. Lamy-Poirier, J. Monteiro, O. Shliazhko, N. Gontier, N. Meade, A. Zebaze, M.-H. Yee, L. K. Umapathi, J. Zhu, B. Lipkin, M. Oblokulov, Z. Wang, R. Murthy, J. Stillerman, S. S. Patel, D. Abulkhanov, M. Zocca, M. Dey, Z. Zhang, N. Fahmy, U. Bhattacharyya, W. Yu, S. Singh, S. Luccioni, P. Villegas, M. Kunakov, F. Zhdanov, M. Romero, T. Lee, N. Timor, J. Ding, C. Schlesinger, H. Schoelkopf, J. Ebert, T. Dao, M. Mishra, A. Gu, J. Robinson, C. J. Anderson, B. Dolan-Gavitt, D. Contractor, S. Reddy, D. Fried, D. Bahdanau, Y. Jernite, C. Muñoz Ferrandis, S. Hughes, T. Wolf, A. Guha, L. von Werra and H. de Vries, "StarCoder: May the source be with you!," _Transactions on Machine Learning Research_, 2023.
+ M. Chen, J. Tworek, H. Jun, Q. Yuan, H. Ponde de Oliveira Pinto, J. Kaplan, H. Edwards, Y. Burda, N. Joseph, G. Brockman, A. Ray, R. Puri, G. Krueger, M. Petrov, H. Khlaaf, G. Sastry, P. Mishkin, B. Chan, S. Gray, N. Ryder, M. Pavlov, A. Power, L. Kaiser, M. Bavarian, C. Winter, P. Tillet, F. Petroski Such, D. Cummings, M. Plappert, F. Chantzis, E. Barnes, A. Herbert-Voss, W. H. Guss, A. Nichol, A. Paino, N. Tezak, J. Tang, I. Babuschkin, S. Balaji, S. Jain, W. Saunders, C. Hesse, A. N. Carr, J. Leike, J. Achiam, V. Misra, E. Morikawa, A. Radford, M. Knight, M. Brundage, M. Murati, K. Mayer, P. Welinder, B. McGrew, D. Amodei, S. McCandlish, I. Sutskever and W. Zaremba, "Evaluating large language models trained on code," arXiv:2107.03374, 2021.
+ D. Guo, Q. Zhu, D. Yang, Z. Xie, K. Dong, W. Zhang, G. Chen, X. Bi, Y. Wu, Y. K. Li, F. Luo, Y. Xiong and W. Liang, "DeepSeek-Coder: When the large language model meets programming – The rise of code intelligence," arXiv:2401.14196, 2024.
+ N. F. Liu, K. Lin, J. Hewitt, A. Paranjape, M. Bevilacqua, F. Petroni and P. Liang, "Lost in the middle: How language models use long contexts," _Transactions of the ACL_, vol. 12, pp. 157–173, 2024.
+ V. Karpukhin, B. Oğuz, S. Min, P. Lewis, L. Wu, S. Edunov, D. Chen and W.-t. Yih, "Dense passage retrieval for open-domain question answering," in _Proc. EMNLP_, pp. 6769–6781, 2020.
+ R. Bairi, A. Sonwane, A. Kanade, V. D. C, A. Iyer, S. Parthasarathy, S. Rajamani, B. Ashok and S. Shet, "CodePlan: Repository-level coding using LLMs and planning," _Proc. ACM on Software Engineering_, vol. 1, no. FSE, pp. 675–698, 2024.
+ F. Yamaguchi, N. Golde, D. Arp and K. Rieck, "Modeling and discovering vulnerabilities with code property graphs," in _IEEE Symposium on Security and Privacy_, pp. 590–604, 2014.
+ J. Ferrante, K. J. Ottenstein and J. D. Warren, "The program dependence graph and its use in optimization," _ACM TOPLAS_, vol. 9, no. 3, pp. 319–349, 1987.
+ S. Ouyang, W. Yu, K. Ma, Z. Xiao, Z. Zhang, M. Jia, J. Han, H. Zhang and D. Yu, "RepoGraph: Enhancing AI software engineering with repository-level code graph," in _Proc. ICLR_, 2025.
+ X. Liu, B. Lan, Z. Hu, Y. Liu, Z. Zhang, F. Wang, M. Shieh and W. Zhou, "CodexGraph: Bridging large language models and code repositories via code graph databases," in _Proc. NAACL_, pp. 142–160, 2025.
+ Z. Chen, X. Tang, G. Deng, F. Wu, J. Wu, Z. Jiang, V. Prasanna, A. Cohan and X. Wang, "LocAgent: Graph-guided LLM agents for code localization," in _Proc. 63rd Annual Meeting of the ACL (Long Papers)_, pp. 8697–8727, 2025.
+ Z. Z. Wang, A. Asai, X. V. Yu, F. F. Xu, Y. Xie, G. Neubig and D. Fried, "CodeRAG-Bench: Can retrieval augment code generation?," in _Findings of NAACL_, 2025.
+ X. Li, K. Dong, Y. Q. Lee, W. Xia, H. Zhang, X. Dai, Y. Wang and R. Tang, "CoIR: A comprehensive benchmark for code information retrieval models," in _Proc. 63rd Annual Meeting of the ACL (Long Papers)_, pp. 22074–22091, 2025.
+ N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese BERT-networks," in _Proc. EMNLP-IJCNLP_, pp. 3980–3990, 2019.
+ S. Xiao, Z. Liu, P. Zhang, N. Muennighoff, D. Lian and J.-Y. Nie, "C-Pack: Packed resources for general Chinese embeddings," in _Proc. 47th ACM SIGIR_, pp. 641–649, 2024.
+ C. E. Jimenez, J. Yang, A. Wettig, S. Yao, K. Pei, O. Press and K. Narasimhan, "SWE-bench: Can language models resolve real-world GitHub issues?," in _Proc. ICLR_, 2024.
+ C. S. Xia, Y. Deng, S. Dunn and L. Zhang, "Demystifying LLM-based software engineering agents," _Proc. ACM on Software Engineering_, vol. 2, no. FSE, pp. 801–824, 2025.
+ H. Husain, H.-H. Wu, T. Gazit, M. Allamanis and M. Brockschmidt, "CodeSearchNet challenge: Evaluating the state of semantic code search," arXiv:1909.09436, 2019.
+ S. Holm, "A simple sequentially rejective multiple test procedure," _Scandinavian Journal of Statistics_, vol. 6, no. 2, pp. 65–70, 1979.

#heading(numbering: none)[Appendix A: Metric Definitions]

For a question $q$, the ranked files are $hat(F)_q = [hat(f)_1, dots, hat(f)_k]$ and the correct files are $F_q^*$. The returned edges are $hat(E)_q$ and the correct edges are $E_q^*$.

$ "Hit@"K(q) = bb(1)[exists i <= K : hat(f)_i in F_q^*], quad "MRR"(q) = 1 / (min {i <= K : hat(f)_i in F_q^*}) " (0 if none)" $

$ "CappedRecall@"10(q) = (|{hat(f)_1, dots, hat(f)_10} inter F_q^*|) / (min(10, |F_q^*|)) $

$ "nDCG@"K(q) = (sum_(i=1)^K bb(1)[hat(f)_i in F_q^*] \/ log_2 (i + 1)) / (sum_(i=1)^(min(K, |F_q^*|)) 1 \/ log_2 (i + 1)) $

$ P(q) = (|hat(E)_q inter E_q^*|) / (|hat(E)_q|), quad R(q) = (|hat(E)_q inter E_q^*|) / (|E_q^*|), quad F_1 = (2 P R) / (P + R) $

If no edges are returned, precision is 0. All scores are averages over questions. We use $K = 7$ for the locate and importer metrics and $K = 10$ for impact. When an importer or impact question names a file, that file is removed from every ranking.

#heading(numbering: none)[Appendix B: Sensitivity Analyses]

#heading(level: 2, numbering: none)[B.1 Fusion weights]

#tbl([RRF LSA + graph on held-out JS with comments removed, for different values of the LSA weight $w_"LSA"$ (the graph weight is $1 - w_"LSA"$) and of $k_0$. The score is MRR for locate and importers and nDCG\@10 for impact. Our pre-set values are $w_"LSA" = 0.55$ and $k_0 = 60$. For every question type and every $k_0$, one of the two lowest LSA weights (0.2 or 0.35) is the best, although the trend is not monotone everywhere. This shows that LSA is a weak member; it does not show that fusion is useful.])[
  #fusion-sweep
]

#heading(level: 2, numbering: none)[B.2 Ranking cut-off]

#tbl([Held-out JS with comments removed: the cut-off $K = 7$ of the main tables next to $K = 10$. The order of the rankers stays the same.])[
  #k-table
]

#heading(numbering: none)[Appendix C: Effect of Indexing Comments] <app-comments>

Previous versions of this evaluation indexed files based on their associated comments. Given that the questions are generated from the comments, the relevant question text was then copied verbatim into the answer file for 340 out of 344 questions, allowing exact matching of keywords. @tab-comments compares the MRRs of locate based on the two different setups. In the absence of comments, the performance of BM25 goes down from 0.85–0.92 to 0.32–0.44, whereas the performance of graph ranker, working only on names, is unaffected. All results in the main text come from the corrected setting, with comments removed.

#tbl([Locate MRR when comments are indexed (the earlier, flawed setting) and when they are removed (the setting of this report).])[
  #leak-table
] <tab-comments>

#heading(numbering: none)[Appendix D: Reproducing the Results]

The code is available at #link("https://github.com/Capstone-TEAM-VITAP/Capstone-VibeLearning")[`github.com/Capstone-TEAM-VITAP/Capstone-VibeLearning`]. Run all commands from the root of the repository, either in Git Bash (Windows) or in a POSIX shell. `PY` is the Python of the analyzer's virtual environment, and `EPY` is a second environment that contains the embedding model. On Linux or macOS, use `bin/python` in place of `Scripts/python`.

```text
bash research/scripts/fetch_repos.sh                          # pinned commits from research/repos.json
python -m venv apps/ai-service/.venv && PY=apps/ai-service/.venv/Scripts/python
$PY -m pip install -r apps/ai-service/requirements.txt
(cd apps/ai-service && .venv/Scripts/python -m pytest -q)     # 856 analyzer tests
$PY research/scripts/analyze_repos.py                         # Graph IR for every repository

python -m venv research/.venv-emb && EPY=research/.venv-emb/Scripts/python
$EPY -m pip install --index-url https://download.pytorch.org/whl/cpu torch
$EPY -m pip install sentence-transformers numpy matplotlib tree-sitter==0.25.2 \
     tree-sitter-javascript==0.25.0 tree-sitter-python==0.25.0

cd research/py && export PYTHONPATH=../../apps/ai-service
../.venv-emb/Scripts/python build_questions_v3.py             # data/questions_v3.json
../.venv-emb/Scripts/python run_retrieval.py                  # out/hybrid_tables.md (about 15 min on CPU)
../.venv-emb/Scripts/python run_flows.py                      # out/flows_tables.md
../.venv-emb/Scripts/python run_accuracy.py                   # out/accuracy_tables.md
../.venv-emb/Scripts/python make_tables.py                    # paper/tables.typ, out/significance.md
../.venv-emb/Scripts/python make_figures.py && ../.venv-emb/Scripts/python make_diagrams.py
cd ../.. && typst compile research/paper/Report.typ
```

The components are in these files: `apps/ai-service/src/repository/python_lang.py` (Python extraction), `resolver.py` (import resolution), `src/retrieval/filegraph.py`, `hybrid.py`, `lsa.py`, `pruner.py`; `research/py/dense.py` (neural ranker), `common.py` (comment stripping and its check, Holm), `oracle.py` (import and call oracles).
