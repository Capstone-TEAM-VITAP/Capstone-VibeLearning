import { useState, useRef, useEffect } from "react";
import {
  Bot,
  Brain,
  Check,
  CircleX,
  Copy,
  Database,
  FileText,
  FolderOpen,
  Layers,
  Lock,
  CirclePlus,
  Send,
  Sparkles,
  Trash2,
  User,
  Webhook,
  Wrench,
} from "lucide-react";
import { askRepoQuestion } from "../services/api.js";
import "./AIAssistant.css";

const PROMPT_ICONS = {
  architecture: Layers,
  api: Webhook,
  lock: Lock,
  database: Database,
  add_circle: CirclePlus,
};

const DEFAULT_PROMPTS = [
  {
    icon: "architecture",
    text: "Explain the architecture and main components of this repository",
  },
  {
    icon: "api",
    text: "Where are the API routes and controllers defined in this codebase?",
  },
  {
    icon: "lock",
    text: "How is authentication and authorization handled?",
  },
  {
    icon: "database",
    text: "What database models exist and how are they structured?",
  },
  {
    icon: "add_circle",
    text: "How can I add a new route or feature to this repository?",
  },
];

/**
 * Parse non-code markdown into structured blocks (headers, lists, tables, blockquotes, paragraphs).
 */
function parseMarkdownBlocks(text) {
  if (!text) return [];
  const lines = text.split(/\r?\n/);
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // Headings
    if (trimmed.startsWith("# ")) {
      blocks.push({ type: "h1", content: trimmed.slice(2) });
      i++;
      continue;
    }
    if (trimmed.startsWith("## ")) {
      blocks.push({ type: "h2", content: trimmed.slice(3) });
      i++;
      continue;
    }
    if (trimmed.startsWith("### ")) {
      blocks.push({ type: "h3", content: trimmed.slice(4) });
      i++;
      continue;
    }
    if (trimmed.startsWith("#### ")) {
      blocks.push({ type: "h4", content: trimmed.slice(5) });
      i++;
      continue;
    }

    // Blockquote
    if (trimmed.startsWith(">")) {
      const qLines = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        qLines.push(lines[i].trim().replace(/^>\s?/, ""));
        i++;
      }
      blocks.push({ type: "blockquote", content: qLines.join(" ") });
      continue;
    }

    // Markdown Table: lines starting and ending with '|'
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }
      if (tableLines.length >= 2) {
        const parseRow = (r) =>
          r
            .slice(1, -1)
            .split("|")
            .map((c) => c.trim());
        const rawRows = tableLines.map(parseRow);
        const sepIndex = rawRows.findIndex((row) =>
          row.every((cell) => /^:?-+:?$/.test(cell))
        );
        let headers = [];
        let rows = [];
        if (sepIndex > 0) {
          headers = rawRows[0];
          rows = rawRows.slice(sepIndex + 1);
        } else {
          headers = rawRows[0];
          rows = rawRows.slice(1);
        }
        blocks.push({ type: "table", headers, rows });
        continue;
      }
    }

    // Unordered list: starts with '- ' or '* ' or '+ '
    if (/^[-*+]\s+/.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^[-*+]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*+]\s+/, ""));
        i++;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    // Ordered list: starts with '1. ', '2. ', etc.
    if (/^\d+\.\s+/.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ""));
        i++;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    // Regular paragraph: collect consecutive non-empty lines until a special block indicator
    const pLines = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("#") &&
      !lines[i].trim().startsWith(">") &&
      !(lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) &&
      !/^[-*+]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim())
    ) {
      pLines.push(lines[i].trim());
      i++;
    }
    if (pLines.length > 0) {
      blocks.push({ type: "p", content: pLines.join(" ") });
    }
  }

  return blocks;
}

function renderBlock(block, bIdx) {
  switch (block.type) {
    case "h1":
      return <h1 key={bIdx}>{formatInline(block.content)}</h1>;
    case "h2":
      return <h2 key={bIdx}>{formatInline(block.content)}</h2>;
    case "h3":
      return <h3 key={bIdx}>{formatInline(block.content)}</h3>;
    case "h4":
      return <h4 key={bIdx}>{formatInline(block.content)}</h4>;
    case "blockquote":
      return <blockquote key={bIdx}>{formatInline(block.content)}</blockquote>;
    case "ul":
      return (
        <ul key={bIdx}>
          {block.items.map((it, itIdx) => (
            <li key={itIdx}>{formatInline(it)}</li>
          ))}
        </ul>
      );
    case "ol":
      return (
        <ol key={bIdx}>
          {block.items.map((it, itIdx) => (
            <li key={itIdx}>{formatInline(it)}</li>
          ))}
        </ol>
      );
    case "table":
      return (
        <div key={bIdx} className="ai-table-wrapper">
          <table className="ai-markdown-table">
            <thead>
              <tr>
                {block.headers.map((h, hIdx) => (
                  <th key={hIdx}>{formatInline(h)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, rIdx) => (
                <tr key={rIdx}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx}>{formatInline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "p":
    default:
      return <p key={bIdx}>{formatInline(block.content)}</p>;
  }
}

/**
 * Lightweight inline markdown renderer for code blocks, headers, tables, lists, bold, and code.
 */
function MarkdownRenderer({ content, onCopyCode, copiedCodeId }) {
  if (!content) return null;

  // Split by code blocks ```...```
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="ai-markdown-body">
      {parts.map((part, index) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const lines = part.slice(3, -3).trim().split("\n");
          let lang = "code";
          let codeLines = lines;
          if (lines[0] && /^[a-zA-Z0-9_-]+$/.test(lines[0].trim())) {
            lang = lines[0].trim();
            codeLines = lines.slice(1);
          }
          const rawCode = codeLines.join("\n");
          const blockId = `code-${index}`;
          const isCopied = copiedCodeId === blockId;

          return (
            <div key={index} className="ai-code-block">
              <div className="ai-code-header">
                <span>{lang}</span>
                <button
                  type="button"
                  className="ai-code-copy-btn"
                  onClick={() => onCopyCode(rawCode, blockId)}
                  title="Copy code"
                >
                  {isCopied ? <Check size={13} /> : <Copy size={13} />}
                  <span>{isCopied ? "Copied!" : "Copy"}</span>
                </button>
              </div>
              <pre className="ai-code-pre">
                <code>{rawCode}</code>
              </pre>
            </div>
          );
        }

        const blocks = parseMarkdownBlocks(part);
        return (
          <div key={index} className="ai-markdown-section">
            {blocks.map((block, bIdx) => renderBlock(block, bIdx))}
          </div>
        );
      })}
    </div>
  );
}

function formatInline(text) {
  if (!text) return "";
  // Split by inline markdown tokens: `code`, **bold**, *italic*, [label](url)
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g;
  const tokens = text.split(regex);

  return tokens.map((token, idx) => {
    if (!token) return null;

    if (token.startsWith("`") && token.endsWith("`") && token.length >= 2) {
      return <code key={idx}>{token.slice(1, -1)}</code>;
    }
    if (token.startsWith("**") && token.endsWith("**") && token.length >= 4) {
      return <strong key={idx}>{token.slice(2, -2)}</strong>;
    }
    if (token.startsWith("*") && token.endsWith("*") && token.length >= 2) {
      return <em key={idx}>{token.slice(1, -1)}</em>;
    }
    const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      return (
        <a
          key={idx}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="ai-markdown-link"
        >
          {linkMatch[1]}
        </a>
      );
    }
    return token;
  });
}

function AIAssistant({
  getToken,
  selectedRepo,
  latestSelectedSnapshot,
  graphData,
  setView,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copiedCodeId, setCopiedCodeId] = useState(null);
  const [activeModel, setActiveModel] = useState("Repo Intelligence");

  const chatFeedRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll chat to bottom when new messages arrive
  useEffect(() => {
    if (chatFeedRef.current) {
      chatFeedRef.current.scrollTop = chatFeedRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const repoName = selectedRepo
    ? `${selectedRepo.owner}/${selectedRepo.name}`
    : "No repository selected";
  const branchName = selectedRepo?.defaultBranch || "main";
  const commitShort = latestSelectedSnapshot?.commitSha
    ? latestSelectedSnapshot.commitSha.slice(0, 7)
    : "HEAD";

  const isAnalyzed = Boolean(graphData && graphData.schema_version === "1.0");

  function handleCopy(code, blockId) {
    if (!code) return;
    navigator.clipboard.writeText(code).then(() => {
      setCopiedCodeId(blockId);
      setTimeout(() => setCopiedCodeId(null), 2000);
    });
  }

  async function handleSend(textToSend) {
    const query = (textToSend || input).trim();
    if (!query || isLoading) return;

    if (!selectedRepo?.id) {
      setError("Please connect or select a repository first.");
      return;
    }

    const userMessage = {
      id: `msg-${Date.now()}-user`,
      role: "user",
      content: query,
      timestamp: new Date(),
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setError(null);
    setIsLoading(true);

    try {
      // Build lightweight conversation history for the LLM
      const history = newMessages
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await askRepoQuestion(getToken, selectedRepo.id, query, history);

      if (res?.model) {
        setActiveModel(res.model);
      }

      const assistantMessage = {
        id: `msg-${Date.now()}-assistant`,
        role: "assistant",
        content: res.message || "No answer generated.",
        citations: res.citations || [],
        model: res.model || "CodeAI Assistant",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      console.error("AI question failed:", err);
      setError(err.message || "Failed to get an answer. Please try again.");
    } finally {
      setIsLoading(false);
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleClearChat() {
    setMessages([]);
    setError(null);
  }

  if (!selectedRepo) {
    return (
      <div className="ai-assistant-container">
        <div className="ai-welcome-card" style={{ margin: "auto" }}>
          <div className="ai-welcome-icon-box">
            <FolderOpen size={28} />
          </div>
          <h3>No Repository Connected</h3>
          <p>Connect a GitHub repository to ask questions about its code, routes, and architecture.</p>
          <button
            type="button"
            className="ws-btn ws-btn-primary"
            onClick={() => setView && setView("repos")}
          >
            Connect Repository
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="ai-assistant-container" data-testid="ai-assistant-workspace">
      {/* Header Context Bar */}
      <header className="ai-assistant-header">
        <div className="ai-header-left">
          <div className="ai-avatar-icon">
            <Sparkles size={18} />
          </div>
          <div className="ai-header-title-group">
            <h2>
              Repository AI Assistant
              <span className={`ai-badge ${isAnalyzed ? "ai-badge-ready" : ""}`}>
                <span className="ai-badge-dot" />
                {isAnalyzed ? "CodeGraph Indexed" : "Snapshot Ready"}
              </span>
            </h2>
            <p>
              Grounded in <strong>{repoName}</strong> · branch <code>{branchName}</code> · commit <code>{commitShort}</code>
            </p>
          </div>
        </div>

        <div className="ai-header-actions">
          {messages.length > 0 && (
            <button
              type="button"
              className="ws-btn ws-btn-ghost"
              style={{ fontSize: 12, padding: "4px 10px" }}
              onClick={handleClearChat}
              title="Clear chat history"
            >
              <Trash2 size={14} />
              Clear Chat
            </button>
          )}

          {!isAnalyzed && (
            <button
              type="button"
              className="ws-btn ws-btn-secondary"
              style={{ fontSize: 12, padding: "4px 10px" }}
              onClick={() => setView && setView("analysis")}
            >
              <Wrench size={14} />
              Analyze Repo
            </button>
          )}
        </div>
      </header>

      {/* Main Conversation Feed */}
      <div className="ai-chat-feed" ref={chatFeedRef}>
        {messages.length === 0 ? (
          <div className="ai-welcome-card">
            <div className="ai-welcome-icon-box">
              <Brain size={28} />
            </div>
            <h3>Ask anything about {repoName}</h3>
            <p>
              I understand the architecture, routes, database models, and functions of this repository.
              Click a suggested question below or type your own.
            </p>

            <div className="ai-prompts-grid">
              {DEFAULT_PROMPTS.map((prompt, idx) => {
                const PromptIcon = PROMPT_ICONS[prompt.icon] ?? Sparkles;
                return (
                  <button
                    key={idx}
                    type="button"
                    className="ai-prompt-chip"
                    onClick={() => handleSend(prompt.text)}
                    disabled={isLoading}
                  >
                    <span className="ai-prompt-chip-icon">
                      <PromptIcon size={15} />
                    </span>
                    <span>{prompt.text}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`ai-message-row ${msg.role}`}>
              <div className="ai-message-avatar">
                {msg.role === "user" ? <User size={16} /> : <Sparkles size={16} />}
              </div>
              <div className="ai-message-bubble">
                {msg.role === "user" ? (
                  <span>{msg.content}</span>
                ) : (
                  <>
                    <MarkdownRenderer
                      content={msg.content}
                      onCopyCode={handleCopy}
                      copiedCodeId={copiedCodeId}
                    />

                    {msg.citations && msg.citations.length > 0 && (
                      <div className="ai-citations-list">
                        <span style={{ fontSize: 11, color: "var(--text-muted)", alignSelf: "center" }}>
                          Referenced files:
                        </span>
                        {msg.citations.map((c, cIdx) => (
                          <span key={cIdx} className="ai-citation-pill" title={`Lines ${c.startLine}-${c.endLine}`}>
                            <FileText size={13} />
                            {c.path}:{c.startLine}
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))
        )}

        {/* Loading Thinking State */}
        {isLoading && (
          <div className="ai-message-row assistant">
            <div className="ai-message-avatar">
              <Sparkles size={16} />
            </div>
            <div className="ai-message-bubble">
              <div className="ai-thinking-indicator">
                <div className="ai-thinking-dots">
                  <div className="ai-thinking-dot" />
                  <div className="ai-thinking-dot" />
                  <div className="ai-thinking-dot" />
                </div>
                <span>Analyzing repository context & generating answer...</span>
              </div>
            </div>
          </div>
        )}

        {/* Error notification */}
        {error && (
          <div className="intel-notice-card" style={{ margin: "10px 0", borderColor: "var(--status-error)" }}>
            <div className="intel-notice-icon" style={{ color: "var(--status-error)" }}>
              <CircleX size={24} />
            </div>
            <p style={{ margin: 0, color: "var(--text-primary)" }}>{error}</p>
          </div>
        )}
      </div>

      {/* Input Bar */}
      <footer className="ai-input-wrapper">
        <form
          className="ai-input-form"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
        >
          <textarea
            ref={textareaRef}
            className="ai-input-textarea"
            rows={1}
            placeholder={`Ask a question about ${selectedRepo.name}... (Press Enter to send, Shift+Enter for newline)`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            type="submit"
            className="ai-send-btn"
            disabled={!input.trim() || isLoading}
            title="Send message (Enter)"
          >
            <Send size={16} />
          </button>
        </form>

        <div className="ai-input-footer">
          <span>Press <strong>Enter</strong> to send, <strong>Shift + Enter</strong> for new lines</span>
          <span className="ai-model-tag">
            <span style={{ color: "var(--tertiary-light)", display: "inline-flex" }}>
              <Bot size={13} />
            </span>
            {activeModel}
          </span>
        </div>
      </footer>
    </div>
  );
}

export default AIAssistant;
