import React, { useState } from "react";
import { SignInButton, SignUpButton } from "@clerk/react";
import {
  ArrowRight,
  Sparkles,
  Cpu,
  Bot,
  Network,
  Route,
  GraduationCap,
  GitPullRequest,
  GitBranch,
  Layers,
  Database,
  CheckCircle2,
  Terminal,
  ShieldCheck,
  ChevronRight,
  ExternalLink,
  Code2,
  Search,
  BookOpen,
  FolderGit2,
  FileCode,
  Zap,
} from "lucide-react";
import ThemeToggle from "./ThemeToggle.jsx";
import "./LandingPage.css";

export default function LandingPage() {
  const [activePreviewTab, setActivePreviewTab] = useState("graph");
  const [activeQuizChoice, setActiveQuizChoice] = useState(null);

  return (
    <div className="landing-wrapper">
      {/* Background illumination & grid overlay */}
      <div className="landing-grid-bg" />

      <div className="landing-content">
        {/* =========================================================
            1. STICKY TOP NAVIGATION BAR
            ========================================================= */}
        <header className="landing-nav">
          <div className="landing-nav-container">
            <a href="#" className="landing-brand">
              <div className="landing-logo-icon">
                <Network className="w-5 h-5 text-white" />
              </div>
              <span className="landing-brand-text" data-testid="brand-title">
                CodeAI
              </span>
              <span className="landing-brand-badge">Capstone</span>
            </a>

            <nav>
              <ul className="landing-nav-links">
                <li>
                  <a href="#features" className="landing-nav-link">
                    Features
                  </a>
                </li>
                <li>
                  <a href="#how-it-works" className="landing-nav-link">
                    How It Works
                  </a>
                </li>
                <li>
                  <a href="#preview" className="landing-nav-link">
                    Product Preview
                  </a>
                </li>
                <li>
                  <a href="#about" className="landing-nav-link">
                    Research & Architecture
                  </a>
                </li>
              </ul>
            </nav>

            <div className="landing-nav-actions">
              <ThemeToggle />
              <SignInButton mode="modal">
                <button
                  className="landing-btn-secondary py-1.5 px-3.5 text-xs"
                  data-testid="sign-in-btn"
                >
                  Sign In
                </button>
              </SignInButton>
              <SignUpButton mode="modal">
                <button
                  className="landing-btn-primary py-1.5 px-4 text-xs"
                  data-testid="sign-up-btn"
                >
                  Sign Up
                </button>
              </SignUpButton>
            </div>
          </div>
        </header>

        {/* =========================================================
            2. HERO SECTION
            ========================================================= */}
        <section className="landing-hero" data-testid="hero-card">
          <div className="landing-hero-grid">
            {/* Left Hero Column */}
            <div className="landing-hero-left">
              <div className="landing-pill-badge">
                <Sparkles className="w-3.5 h-3.5 landing-pill-sparkle" />
                <span>Next-Gen Repository Intelligence • Final Year Capstone</span>
              </div>

              <h1 className="landing-hero-title">
                Understand Your Codebase. <br />
                <span className="landing-gradient-text">Build Smarter.</span>
              </h1>

              <p className="landing-hero-desc">
                CodeAI transforms your GitHub repositories into intelligent, interactive
                knowledge systems. Explore code architecture, understand execution flows,
                generate insights, and improve your development skills with AI.
              </p>

              <div className="landing-hero-ctas">
                <SignUpButton mode="modal">
                  <button
                    className="landing-btn-primary"
                    data-testid="hero-get-started-btn"
                  >
                    Get Started
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </SignUpButton>

                <a href="#features" className="landing-btn-secondary">
                  <Terminal className="w-4 h-4 text-zinc-400" />
                  Explore Features
                </a>
              </div>

              <div className="landing-tech-stack-row">
                <span className="landing-tech-item">
                  <span className="landing-tech-dot" /> Tree-sitter AST
                </span>
                <span>•</span>
                <span className="landing-tech-item">CodeGraph IR v1.0</span>
                <span>•</span>
                <span className="landing-tech-item">Express 5 & FastAPI</span>
                <span>•</span>
                <span className="landing-tech-item">Prisma 8 ORM</span>
              </div>
            </div>

            {/* Right Hero Column: Interactive Terminal Preview */}
            <div className="landing-hero-preview">
              <div className="landing-terminal-glow" />
              <div className="landing-terminal-window">
                <div className="landing-terminal-header">
                  <div className="landing-terminal-dots">
                    <span className="landing-dot red" />
                    <span className="landing-dot yellow" />
                    <span className="landing-dot green" />
                  </div>
                  <span className="landing-terminal-title">
                    codeai-workstation / expressjs-session
                  </span>
                  <div className="landing-terminal-status">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Graph Ready
                  </div>
                </div>

                <div className="landing-terminal-body">
                  <div className="landing-terminal-repo-info">
                    <div className="landing-terminal-repo-name">
                      <FolderGit2 className="w-3.5 h-3.5 text-zinc-400" />
                      <span>expressjs / session</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-zinc-500 text-[11px]">42 files</span>
                      <span className="landing-terminal-sha">main : f8c297e</span>
                    </div>
                  </div>

                  {/* Flow Trace Mini Visualization */}
                  <div className="landing-mini-graph">
                    <div className="text-[10.5px] font-mono text-zinc-400 flex items-center justify-between pb-1 border-b border-zinc-800">
                      <span>EXECUTION CHAIN RESOLUTION</span>
                      <span className="text-emerald-400">100% Resolved</span>
                    </div>

                    <div className="landing-mini-node">
                      <div className="landing-node-label">
                        <Route className="w-3.5 h-3.5 text-cyan-400" />
                        <span>GET /api/v1/auth/me</span>
                      </div>
                      <span className="landing-node-tag tag-router">ROUTER</span>
                    </div>

                    <div className="landing-graph-arrow">↓ CALLS</div>

                    <div className="landing-mini-node active">
                      <div className="landing-node-label">
                        <Code2 className="w-3.5 h-3.5 text-purple-400" />
                        <span>authController.getMe()</span>
                      </div>
                      <span className="landing-node-tag tag-controller">CONTROLLER</span>
                    </div>

                    <div className="landing-graph-arrow">↓ DELEGATES</div>

                    <div className="landing-mini-node">
                      <div className="landing-node-label">
                        <Layers className="w-3.5 h-3.5 text-emerald-400" />
                        <span>authService.validateSession()</span>
                      </div>
                      <span className="landing-node-tag tag-service">SERVICE</span>
                    </div>

                    <div className="landing-graph-arrow">↓ QUERIES</div>

                    <div className="landing-mini-node">
                      <div className="landing-node-label">
                        <Database className="w-3.5 h-3.5 text-orange-400" />
                        <span>SessionStore.findUnique()</span>
                      </div>
                      <span className="landing-node-tag tag-model">POSTGRES</span>
                    </div>
                  </div>

                  {/* Context-Grounded AI Callout */}
                  <div className="landing-ai-callout">
                    <Bot className="w-4 h-4 landing-ai-callout-icon" />
                    <div className="landing-ai-callout-text">
                      <strong>AI Context Grounding:</strong> Extracted 89 symbols and 142
                      dependencies. Zero hallucinations.
                      <span className="landing-ai-callout-cite">
                        Citation: apps/backend/src/services/auth.service.js#L28-L54
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* =========================================================
            3. FEATURES SECTION
            ========================================================= */}
        <section id="features" className="landing-section">
          <div className="landing-section-header">
            <div className="landing-section-eyebrow">DEEP ARCHITECTURAL CAPABILITIES</div>
            <h2 className="landing-section-title">
              Engineered for Complete Repository Understanding
            </h2>
            <p className="landing-section-desc">
              Move beyond flat text files. CodeAI builds a queryable structural graph of
              your entire system, mapping execution flows from entry points to database stores.
            </p>
          </div>

          <div className="landing-features-grid">
            {/* Feature 1 */}
            <div className="landing-feature-card card-cyan">
              <div className="landing-feature-icon-wrapper">
                <Cpu className="w-5 h-5" />
              </div>
              <div className="landing-feature-header-row">
                <h3 className="landing-feature-title">Repository Intelligence</h3>
                <span className="landing-feature-tag">AST Parsing</span>
              </div>
              <p className="landing-feature-desc">
                Automated multi-pass ingestion using language-specific Tree-sitter parsers.
                Classifies architectural layers, file topologies, and dependency health.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="landing-feature-card card-indigo">
              <div className="landing-feature-icon-wrapper">
                <Bot className="w-5 h-5" />
              </div>
              <div className="landing-feature-header-row">
                <h3 className="landing-feature-title">AI Software Assistant</h3>
                <span className="landing-feature-tag">Grounded RRF</span>
              </div>
              <p className="landing-feature-desc">
                Context-grounded assistant with strict zero-hallucination guardrails. Answers
                are synthesized from real CodeGraph relationships and exact file line ranges.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="landing-feature-card card-purple">
              <div className="landing-feature-icon-wrapper">
                <Network className="w-5 h-5" />
              </div>
              <div className="landing-feature-header-row">
                <h3 className="landing-feature-title">Interactive Code Graph</h3>
                <span className="landing-feature-tag">React Flow</span>
              </div>
              <p className="landing-feature-desc">
                Interactive multi-hop visualization of calls, imports, and definitions. Filter
                by layer, trace callers and callees, and isolate circular dependencies.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="landing-feature-card card-emerald">
              <div className="landing-feature-icon-wrapper">
                <Route className="w-5 h-5" />
              </div>
              <div className="landing-feature-header-row">
                <h3 className="landing-feature-title">API & Route Mapping</h3>
                <span className="landing-feature-tag">Flow Discovery</span>
              </div>
              <p className="landing-feature-desc">
                Automatic HTTP route discovery for Express. Resolves mounted routers,
                middleware chains, and controller functions with full source locations.
              </p>
            </div>

            {/* Feature 5 */}
            <div className="landing-feature-card card-amber">
              <div className="landing-feature-icon-wrapper">
                <GraduationCap className="w-5 h-5" />
              </div>
              <div className="landing-feature-header-row">
                <h3 className="landing-feature-title">Developer Learning</h3>
                <span className="landing-feature-tag">Adaptive Quizzes</span>
              </div>
              <p className="landing-feature-desc">
                Personalized conceptual quizzes and commit diff challenges generated
                directly from your code, complete with code excerpts and grading.
              </p>
            </div>

            {/* Feature 6 */}
            <div className="landing-feature-card card-rose">
              <div className="landing-feature-icon-wrapper">
                <GitPullRequest className="w-5 h-5" />
              </div>
              <div className="landing-feature-header-row">
                <h3 className="landing-feature-title">Intelligent Code Review</h3>
                <span className="landing-feature-tag">Impact Analysis</span>
              </div>
              <p className="landing-feature-desc">
                Automated commit change breakdown scoring impact severity, classifying
                structural modifications, and generating explanations of side effects.
              </p>
            </div>
          </div>
        </section>

        {/* =========================================================
            4. HOW IT WORKS SECTION (WORKFLOW)
            ========================================================= */}
        <section id="how-it-works" className="landing-section">
          <div className="landing-section-header">
            <div className="landing-section-eyebrow">EXECUTION PIPELINE</div>
            <h2 className="landing-section-title">
              From Raw GitHub Commits to Interactive Code Intelligence
            </h2>
            <p className="landing-section-desc">
              How CodeAI deterministically processes your codebase across five sequential stages.
            </p>
          </div>

          <div className="landing-workflow-track">
            {/* Step 1 */}
            <div className="landing-step-card">
              <div className="landing-step-number">
                <span>01</span>
                <div className="landing-step-icon">
                  <FolderGit2 className="w-3.5 h-3.5" />
                </div>
              </div>
              <h4 className="landing-step-title">Connect GitHub</h4>
              <p className="landing-step-desc">
                Link public or private repositories. CodeAI caches bare git mirrors and
                resolves commit SHAs with zero token exposure.
              </p>
            </div>

            {/* Step 2 */}
            <div className="landing-step-card">
              <div className="landing-step-number">
                <span>02</span>
                <div className="landing-step-icon">
                  <Cpu className="w-3.5 h-3.5" />
                </div>
              </div>
              <h4 className="landing-step-title">Analyze Repository</h4>
              <p className="landing-step-desc">
                Tree-sitter AST engines traverse every JavaScript, TypeScript, and Python
                source file to extract symbols, scopes, and calls.
              </p>
            </div>

            {/* Step 3 */}
            <div className="landing-step-card">
              <div className="landing-step-number">
                <span>03</span>
                <div className="landing-step-icon">
                  <Network className="w-3.5 h-3.5" />
                </div>
              </div>
              <h4 className="landing-step-title">Build CodeGraph</h4>
              <p className="landing-step-desc">
                Synthesizes canonical Graph IR v1.0 mapping callers, callees, architectural
                layers, and cross-file dependencies.
              </p>
            </div>

            {/* Step 4 */}
            <div className="landing-step-card">
              <div className="landing-step-number">
                <span>04</span>
                <div className="landing-step-icon">
                  <Bot className="w-3.5 h-3.5" />
                </div>
              </div>
              <h4 className="landing-step-title">AI Grounding</h4>
              <p className="landing-step-desc">
                Hybrid RRF fuses lexical BM25, graph path proximity, and dense vectors to
                select exact line excerpts for reasoning.
              </p>
            </div>

            {/* Step 5 */}
            <div className="landing-step-card">
              <div className="landing-step-number">
                <span>05</span>
                <div className="landing-step-icon">
                  <Zap className="w-3.5 h-3.5" />
                </div>
              </div>
              <h4 className="landing-step-title">Actionable Insights</h4>
              <p className="landing-step-desc">
                Explore interactive visual graphs, audit API routes, query the AI assistant,
                and practice with adaptive learning sets.
              </p>
            </div>
          </div>
        </section>

        {/* =========================================================
            5. INTERACTIVE PRODUCT PREVIEW SHOWCASE
            ========================================================= */}
        <section id="preview" className="landing-section">
          <div className="landing-section-header">
            <div className="landing-section-eyebrow">WORKSTATION SHOWCASE</div>
            <h2 className="landing-section-title">A Look Inside the CodeAI Platform</h2>
            <p className="landing-section-desc">
              Explore the four core modules designed for developer onboarding and deep
              architectural analysis.
            </p>
          </div>

          <div className="landing-preview-showcase">
            {/* Tab Controls */}
            <div className="landing-preview-tabs">
              <button
                className={`landing-preview-tab-btn ${activePreviewTab === "graph" ? "active" : ""}`}
                onClick={() => setActivePreviewTab("graph")}
              >
                <Network className="w-4 h-4" />
                Interactive Code Graph
              </button>
              <button
                className={`landing-preview-tab-btn ${activePreviewTab === "routes" ? "active" : ""}`}
                onClick={() => setActivePreviewTab("routes")}
              >
                <Route className="w-4 h-4" />
                API & Route Map
              </button>
              <button
                className={`landing-preview-tab-btn ${activePreviewTab === "assistant" ? "active" : ""}`}
                onClick={() => setActivePreviewTab("assistant")}
              >
                <Bot className="w-4 h-4" />
                AI Assistant Interface
              </button>
              <button
                className={`landing-preview-tab-btn ${activePreviewTab === "quiz" ? "active" : ""}`}
                onClick={() => setActivePreviewTab("quiz")}
              >
                <GraduationCap className="w-4 h-4" />
                Developer Learning Quiz
              </button>
            </div>

            {/* Tab Display Area */}
            <div className="landing-preview-display">
              {activePreviewTab === "graph" && (
                <div className="flex flex-col gap-4 font-mono text-xs">
                  <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
                    <div className="flex items-center gap-3">
                      <span className="text-zinc-400">Node Filter:</span>
                      <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-200">
                        All Layers (7 nodes, 9 edges)
                      </span>
                    </div>
                    <span className="text-cyan-400">Schema Version 1.0 IR</span>
                  </div>

                  <div className="grid grid-cols-3 gap-4 pt-2">
                    <div className="p-3 rounded-lg border border-cyan-500/30 bg-cyan-950/20">
                      <div className="text-cyan-400 font-semibold mb-1">
                        ROUTER: api/v1/auth
                      </div>
                      <div className="text-zinc-400 text-[11px]">
                        File: src/routes/auth.routes.js
                      </div>
                      <div className="mt-2 text-zinc-500 text-[10px]">
                        Out: 2 CALLS &rarr; authController
                      </div>
                    </div>

                    <div className="p-3 rounded-lg border border-purple-500/30 bg-purple-950/20">
                      <div className="text-purple-400 font-semibold mb-1">
                        CONTROLLER: authController.login
                      </div>
                      <div className="text-zinc-400 text-[11px]">
                        File: src/controllers/auth.controller.js
                      </div>
                      <div className="mt-2 text-zinc-500 text-[10px]">
                        Out: 1 CALLS &rarr; authService
                      </div>
                    </div>

                    <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-950/20">
                      <div className="text-emerald-400 font-semibold mb-1">
                        SERVICE: authService.verifyUser
                      </div>
                      <div className="text-zinc-400 text-[11px]">
                        File: src/services/auth.service.js
                      </div>
                      <div className="mt-2 text-zinc-500 text-[10px]">
                        Out: 1 QUERIES &rarr; User (Postgres)
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 text-zinc-300">
                    <div className="text-zinc-400 mb-1 flex items-center gap-2">
                      <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Graph Insight:</span>
                    </div>
                    <span>
                      Clean 3-tier layering detected. Zero circular dependencies. All 14
                      controller exports resolve to valid handler implementations.
                    </span>
                  </div>
                </div>
              )}

              {activePreviewTab === "routes" && (
                <div className="flex flex-col gap-3 font-mono text-xs">
                  <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
                    <div className="flex items-center gap-2">
                      <span className="text-zinc-400">Total Endpoints: 27</span>
                      <span className="text-emerald-400">(25 Resolved, 2 Static)</span>
                    </div>
                    <span className="text-zinc-500">Express AST Scanner</span>
                  </div>

                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between p-2.5 rounded bg-zinc-900/80 border border-zinc-800">
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400">
                          GET
                        </span>
                        <span className="text-zinc-200 font-semibold">
                          /api/v1/auth/me
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-zinc-400">
                        <span>authController.getMe</span>
                        <span className="text-emerald-400 text-[10px]">● RESOLVED</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded bg-zinc-900/80 border border-zinc-800">
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400">
                          POST
                        </span>
                        <span className="text-zinc-200 font-semibold">
                          /api/v1/repos/connect
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-zinc-400">
                        <span>repoController.connectRepo</span>
                        <span className="text-emerald-400 text-[10px]">● RESOLVED</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded bg-zinc-900/80 border border-zinc-800">
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400">
                          PATCH
                        </span>
                        <span className="text-zinc-200 font-semibold">
                          /api/v1/settings
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-zinc-400">
                        <span>settingsController.updateSettings</span>
                        <span className="text-emerald-400 text-[10px]">● RESOLVED</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activePreviewTab === "assistant" && (
                <div className="flex flex-col gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-zinc-900/90 border border-zinc-800 flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-zinc-700 flex items-center justify-center font-bold text-[10px]">
                      U
                    </div>
                    <div className="flex-1">
                      <div className="text-zinc-400 text-[10px] mb-1">Developer Query</div>
                      <div className="text-zinc-200 font-medium">
                        "Where is the GitHub webhook signature verified, and what happens if
                        it fails?"
                      </div>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-indigo-950/20 border border-indigo-500/30 flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-indigo-600 flex items-center justify-center text-white">
                      <Bot className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex-1 space-y-2">
                      <div className="text-indigo-400 text-[10px] font-semibold">
                        CodeAI Grounded Response (Groq Llama 3.3 70B)
                      </div>
                      <p className="text-zinc-300 leading-relaxed">
                        The webhook HMAC signature is verified in{" "}
                        <code className="text-cyan-400">webhookController.handleGithub</code>{" "}
                        using <code className="text-cyan-400">verifySignature()</code> inside{" "}
                        <code className="text-cyan-400">apps/backend/src/utils/github.js</code>.
                        If the SHA-256 HMAC does not match{" "}
                        <code className="text-zinc-400">process.env.GITHUB_WEBHOOK_SECRET</code>,
                        the request halts immediately with a{" "}
                        <strong className="text-rose-400">401 Invalid signature</strong>{" "}
                        response before invoking any repository synchronization.
                      </p>
                      <div className="pt-1 flex items-center gap-2 text-[10.5px] font-mono text-cyan-400">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Cited from apps/backend/src/controllers/webhook.controller.js#L18-L23</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activePreviewTab === "quiz" && (
                <div className="flex flex-col gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800">
                    <div className="flex items-center justify-between text-zinc-400 text-[11px] mb-2 font-mono">
                      <span>QUESTION 1 OF 5 • INTERMEDIATE</span>
                      <span className="text-cyan-400">Topic: Architecture Flow</span>
                    </div>
                    <div className="text-zinc-100 font-medium text-sm mb-3">
                      Which service coordinates the background analysis job and ensures that
                      concurrent requests do not duplicate AI static analysis?
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { id: 0, text: "A. git.service.js using execFileAsync" },
                        {
                          id: 1,
                          text: "B. analysis.service.js with atomic tryAcquireRunning lock",
                          correct: true,
                        },
                        { id: 2, text: "C. repo.controller.js using session cookies" },
                        { id: 3, text: "D. client-side polling in Dashboard.jsx" },
                      ].map((option) => (
                        <button
                          key={option.id}
                          onClick={() => setActiveQuizChoice(option.id)}
                          className={`p-2.5 rounded text-left font-mono transition-all border ${
                            activeQuizChoice === option.id
                              ? option.correct
                                ? "bg-emerald-950/50 border-emerald-500 text-emerald-300"
                                : "bg-rose-950/50 border-rose-500 text-rose-300"
                              : "bg-zinc-900/50 border-zinc-800 text-zinc-300 hover:border-zinc-700"
                          }`}
                        >
                          {option.text}
                        </button>
                      ))}
                    </div>

                    {activeQuizChoice !== null && (
                      <div className="mt-3 p-2.5 rounded bg-zinc-900/90 border border-zinc-800 text-[11px] text-zinc-300">
                        {activeQuizChoice === 1 ? (
                          <span className="text-emerald-400 font-semibold">
                            Correct! analysis.service.js uses PostgreSQL conditional
                            UPDATE locks to enforce single-job execution.
                          </span>
                        ) : (
                          <span className="text-rose-400 font-semibold">
                            Incorrect. analysis.service.js manages atomic job locks.
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* =========================================================
            6. ACADEMIC RESEARCH / CAPSTONE CALLOUT
            ========================================================= */}
        <section id="about" className="landing-section">
          <div className="landing-research-card">
            <div>
              <div className="landing-research-badge">
                <BookOpen className="w-3.5 h-3.5" />
                <span>ARXIV RESEARCH PAPER</span>
              </div>
              <h3 className="landing-research-title">
                When Does Code Structure Help? Evaluating Code Graph Augmentation in
                Repository-Level AI
              </h3>
              <p className="landing-research-desc">
                Developed as a comprehensive final-year engineering capstone project, CodeAI
                benchmarks how static code graph augmentation outperforms isolated BM25
                and raw dense vector retrieval across real-world open-source codebases.
              </p>
            </div>

            <div className="landing-research-metrics">
              <div className="landing-metric-box">
                <div className="landing-metric-value">113</div>
                <div className="landing-metric-label">Backend Tests Passing (100%)</div>
              </div>
              <div className="landing-metric-box">
                <div className="landing-metric-value">878+</div>
                <div className="landing-metric-label">AI Service Tests Verified</div>
              </div>
              <div className="landing-metric-box">
                <div className="landing-metric-value">0%</div>
                <div className="landing-metric-label">Hallucinations (Deterministic IR)</div>
              </div>
              <div className="landing-metric-box">
                <div className="landing-metric-value">₹0</div>
                <div className="landing-metric-label">Cloud Deployment Cost / Month</div>
              </div>
            </div>
          </div>
        </section>

        {/* =========================================================
            7. FOOTER
            ========================================================= */}
        <footer className="landing-footer">
          <div className="landing-footer-container">
            <div className="landing-footer-grid">
              {/* Brand Column */}
              <div>
                <a href="#" className="landing-brand mb-3">
                  <div className="landing-logo-icon">
                    <Network className="w-5 h-5 text-white" />
                  </div>
                  <span className="landing-brand-text">CodeAI</span>
                </a>
                <p className="landing-footer-brand-desc">
                  Transforms GitHub repositories into intelligent, interactive knowledge
                  systems. Built for developer code comprehension, execution tracing, and
                  technical mastery.
                </p>
                <div className="flex items-center gap-3">
                  <SignInButton mode="modal">
                    <button className="landing-btn-secondary py-1.5 px-3 text-xs">
                      Sign In
                    </button>
                  </SignInButton>
                  <SignUpButton mode="modal">
                    <button className="landing-btn-primary py-1.5 px-3.5 text-xs">
                      Get Started
                    </button>
                  </SignUpButton>
                </div>
              </div>

              {/* Col 1: Platform */}
              <div>
                <h5 className="landing-footer-col-title">Platform</h5>
                <ul className="landing-footer-links">
                  <li><a href="#features" className="landing-footer-link">Repository Intelligence</a></li>
                  <li><a href="#preview" className="landing-footer-link">Interactive Code Graph</a></li>
                  <li><a href="#features" className="landing-footer-link">API Route Mapping</a></li>
                  <li><a href="#features" className="landing-footer-link">AI Assistant Interface</a></li>
                  <li><a href="#features" className="landing-footer-link">Developer Quizzes</a></li>
                </ul>
              </div>

              {/* Col 2: Architecture */}
              <div>
                <h5 className="landing-footer-col-title">Architecture</h5>
                <ul className="landing-footer-links">
                  <li><span className="text-zinc-400">Tree-sitter AST (v0.25)</span></li>
                  <li><span className="text-zinc-400">CodeGraph IR (v1.0)</span></li>
                  <li><span className="text-zinc-400">Express 5 ESM Backend</span></li>
                  <li><span className="text-zinc-400">FastAPI AI Microservice</span></li>
                  <li><span className="text-zinc-400">Prisma 8 ORM (PostgreSQL)</span></li>
                </ul>
              </div>

              {/* Col 3: Research */}
              <div>
                <h5 className="landing-footer-col-title">Academic Capstone</h5>
                <ul className="landing-footer-links">
                  <li><a href="#about" className="landing-footer-link">arXiv Research Paper</a></li>
                  <li><span className="text-zinc-400">Reproducible Benchmark Harness</span></li>
                  <li><span className="text-zinc-400">Deterministic RRF Ranking</span></li>
                  <li><span className="text-zinc-400">Google Cloud Run Unified Container</span></li>
                  <li><span className="text-zinc-400">Clerk JWT Authentication</span></li>
                </ul>
              </div>
            </div>

            <div className="landing-footer-bottom">
              <span>© 2026 CodeAI. All rights reserved. Final Year Engineering Capstone.</span>
              <div className="flex items-center gap-6">
                <span>Terminal Horizon Design System</span>
                <span>•</span>
                <span>Production Build Verified</span>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
