import crypto from "node:crypto";

/**
 * Shared text-completion helper for features outside the chat flow.
 *
 * Provider order: OpenCode Go (default model deepseek-v4.1-flash, medium
 * thinking) when OPENCODE_API_KEY is set, otherwise Groq when GROQ_API_KEY is
 * set. Throws when no provider is configured or the call fails, so callers can
 * decide how to degrade.
 */

const DEFAULT_OPENCODE_MODEL = "deepseek-v4.1-flash";

export function getLlmConfig() {
  if (process.env.OPENCODE_API_KEY) {
    return {
      provider: "opencode-go",
      baseUrl: process.env.OPENCODE_BASE_URL || "https://opencode.ai/zen/go/v1",
      apiKey: process.env.OPENCODE_API_KEY,
      model: process.env.OPENCODE_MODEL || DEFAULT_OPENCODE_MODEL,
      reasoningEffort: process.env.OPENCODE_REASONING_EFFORT || "medium",
    };
  }
  if (process.env.GROQ_API_KEY) {
    return {
      provider: "groq",
      baseUrl: process.env.GROQ_BASE_URL || "https://api.groq.com/openai/v1",
      apiKey: process.env.GROQ_API_KEY,
      model: process.env.GROQ_MODEL || "openai/gpt-oss-120b",
      reasoningEffort: null,
    };
  }
  return null;
}

export async function completeText({
  system,
  user,
  maxTokens = 4000,
  sessionKey = "default",
  json = false,
  timeoutMs = 90000,
  fetchImpl = globalThis.fetch,
}) {
  const cfg = getLlmConfig();
  if (!cfg) {
    const err = new Error("No AI provider is configured. Set OPENCODE_API_KEY in apps/backend/.env.");
    err.code = "LLM_NOT_CONFIGURED";
    throw err;
  }

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${cfg.apiKey}`,
  };
  if (cfg.provider === "opencode-go") {
    // OpenCode Go asks clients to identify themselves and send a stable
    // session id per conversation (used for routing and prompt caching).
    const session = crypto.createHash("sha256").update(sessionKey).digest("hex").slice(0, 32);
    headers["User-Agent"] = "CodeAI-Assistant/1.0";
    headers["x-opencode-session"] = `codeai-${session}`;
  }

  const body = {
    model: cfg.model,
    messages: [
      { role: "system", content: system },
      { role: "user", content: user },
    ],
    temperature: 0.2,
    max_tokens: maxTokens,
  };
  if (cfg.reasoningEffort && cfg.reasoningEffort !== "none") {
    body.reasoning_effort = cfg.reasoningEffort;
  }
  if (json) {
    body.response_format = { type: "json_object" };
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetchImpl(`${cfg.baseUrl.replace(/\/+$/, "")}/chat/completions`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    throw new Error(
      err.name === "AbortError" ? `AI provider timed out after ${timeoutMs / 1000}s` : `AI provider unreachable: ${err.message}`,
    );
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`AI provider error (${res.status}): ${text.slice(0, 300)}`);
  }

  const data = await res.json();
  const content = data?.choices?.[0]?.message?.content;
  if (!content) throw new Error("AI provider returned an empty response");
  return { text: content, model: cfg.model, provider: cfg.provider };
}

export default { completeText, getLlmConfig };
