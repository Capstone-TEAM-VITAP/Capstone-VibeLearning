import {
  BadGatewayError,
  BadRequestError,
  GatewayTimeoutError,
  NotFoundError,
  ServiceUnavailableError,
} from "../utils/errors.js";

const DEFAULT_AI_SERVICE_URL = "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 60000;

/**
 * Validate that data strictly adheres to the canonical M8 Graph IR schema.
 */
export function validateGraphIr(ir) {
  if (!ir || typeof ir !== "object" || Array.isArray(ir)) {
    throw new BadGatewayError("Invalid response from AI service: IR must be an object");
  }

  if (ir.schema_version !== "1.0") {
    throw new BadGatewayError(
      `Invalid response from AI service: unsupported schema_version '${ir.schema_version}'`
    );
  }

  if (!ir.repository || typeof ir.repository !== "object" || Array.isArray(ir.repository)) {
    throw new BadGatewayError("Invalid response from AI service: missing repository metadata");
  }

  if (!Array.isArray(ir.nodes)) {
    throw new BadGatewayError("Invalid response from AI service: 'nodes' must be an array");
  }

  if (!Array.isArray(ir.edges)) {
    throw new BadGatewayError("Invalid response from AI service: 'edges' must be an array");
  }

  return true;
}

/**
 * Client for communicating with the Python AI Service.
 */
export const aiService = {
  getBaseUrl() {
    return (process.env.AI_SERVICE_URL || DEFAULT_AI_SERVICE_URL).replace(/\/+$/, "");
  },

  getTimeoutMs() {
    const envVal = process.env.AI_SERVICE_TIMEOUT_MS;
    if (envVal && !isNaN(Number(envVal))) {
      return Number(envVal);
    }
    return DEFAULT_TIMEOUT_MS;
  },

  /**
   * Request static analysis of a local repository from the AI Service.
   *
   * @param {string} repositoryPath Absolute or relative path to the local repository.
   * @param {string} [repositoryName] Optional explicit repository name.
   * @returns {Promise<object>} The canonical Graph IR object.
   */
  async analyzeRepository(repositoryPath, repositoryName) {
    if (!repositoryPath || typeof repositoryPath !== "string" || !repositoryPath.trim()) {
      throw new BadRequestError("repositoryPath is required");
    }

    const baseUrl = this.getBaseUrl();
    const timeoutMs = this.getTimeoutMs();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    let res;
    try {
      res = await fetch(`${baseUrl}/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          repository_path: repositoryPath.trim(),
          repo_name: repositoryName || undefined,
        }),
        signal: controller.signal,
      });
    } catch (err) {
      if (err.name === "AbortError") {
        throw new GatewayTimeoutError("AI service request timed out");
      }
      // Connection refused, DNS failure, etc.
      throw new ServiceUnavailableError("AI service unavailable");
    } finally {
      clearTimeout(timer);
    }

    let payload;
    try {
      payload = await res.json();
    } catch {
      throw new BadGatewayError("Failed to parse JSON response from AI service");
    }

    if (!res.ok) {
      const detail = payload?.detail || payload?.message || "AI service analysis failed";
      // Sanitize internal filesystem paths if exposed in detail message
      const sanitized = typeof detail === "string" ? detail.replace(/[a-zA-Z]:\\[\w\\.-]+/g, "<path>") : "Analysis failed";

      if (res.status === 404) {
        throw new NotFoundError(sanitized);
      }
      if (res.status === 400) {
        throw new BadRequestError(sanitized);
      }
      throw new BadGatewayError(`AI service error (${res.status}): ${sanitized}`);
    }

    if (!payload || typeof payload !== "object" || !payload.ir) {
      throw new BadGatewayError("Invalid response from AI service: missing 'ir' payload");
    }

    // Strictly validate Graph IR schema version 1.0 contract
    validateGraphIr(payload.ir);

    return payload.ir;
  },
};

export default aiService;
