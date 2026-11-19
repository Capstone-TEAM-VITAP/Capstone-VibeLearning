import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "../../");

const AI_DIR = path.join(rootDir, "apps/ai-service");
const BACKEND_DIR = path.join(rootDir, "apps/backend");

console.log("[Test] 1. Launching FastAPI AI service on 127.0.0.1:8000...");
const pyProc = spawn("python", ["-m", "uvicorn", "src.main:app", "--app-dir", AI_DIR, "--host", "127.0.0.1", "--port", "8000"], {
  cwd: AI_DIR,
  stdio: ["ignore", "pipe", "pipe"],
  env: {
    ...process.env,
    CODEAI_ANALYSIS_ROOT: process.env.TEMP || "C:\\temp",
  },
});

pyProc.stdout.on("data", (d) => process.stdout.write(`[FastAPI] ${d}`));
pyProc.stderr.on("data", (d) => process.stderr.write(`[FastAPI] ${d}`));

async function waitHealthy(url, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      // wait
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}

async function run() {
  try {
    const aiReady = await waitHealthy("http://127.0.0.1:8000/health", 15000);
    if (!aiReady) {
      throw new Error("FastAPI AI service failed to start within 15 seconds.");
    }
    console.log("[Test] FastAPI AI service is HEALTHY on http://127.0.0.1:8000/health");

    console.log("[Test] 2. Launching Node.js Express backend on 0.0.0.0:8080 (Cloud Run port)...");
    const nodeProc = spawn("node", ["index.js"], {
      cwd: BACKEND_DIR,
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        PORT: "8080",
        HOST: "0.0.0.0",
        AI_SERVICE_URL: "http://127.0.0.1:8000",
        GIT_CACHE_DIR: path.join(process.env.TEMP || "C:\\temp", "codeai-repos"),
        CODEAI_ANALYSIS_ROOT: path.join(process.env.TEMP || "C:\\temp", "codeai-repos"),
      },
    });

    nodeProc.stdout.on("data", (d) => process.stdout.write(`[Express] ${d}`));
    nodeProc.stderr.on("data", (d) => process.stderr.write(`[Express] ${d}`));

    const backendReady = await waitHealthy("http://127.0.0.1:8080/health", 15000);
    if (!backendReady) {
      throw new Error("Express backend failed to start within 15 seconds.");
    }
    console.log("[Test] Express backend is HEALTHY on http://127.0.0.1:8080/health");

    console.log("[Test] 3. Testing health endpoint verifying both services...");
    const res = await fetch("http://127.0.0.1:8080/health");
    console.log(`[Test] HTTP status: ${res.status}`);
    const data = await res.json();
    console.log("[Test] Health payload:", JSON.stringify(data, null, 2));

    if (res.status !== 200 || data.data?.status !== "healthy") {
      throw new Error(`Expected status 200 and healthy, got ${res.status}`);
    }
    if (data.data?.services?.backend !== "ok" || data.data?.services?.aiService !== "ok") {
      throw new Error(`Services not ok: ${JSON.stringify(data.data?.services)}`);
    }

    console.log("[Test] 4. Testing /api/v1/health endpoint...");
    const resV1 = await fetch("http://127.0.0.1:8080/api/v1/health");
    const dataV1 = await resV1.json();
    if (resV1.status !== 200 || dataV1.data?.status !== "healthy") {
      throw new Error(`Expected /api/v1/health status 200 and healthy`);
    }
    console.log("[Test] /api/v1/health verification SUCCESSFUL!");

    console.log("[Test] 5. Testing graceful shutdown (SIGTERM)...");
    nodeProc.kill("SIGTERM");
    await new Promise((r) => nodeProc.on("exit", r));
    console.log("[Test] Express exited gracefully.");

    pyProc.kill("SIGTERM");
    await new Promise((r) => pyProc.on("exit", r));
    console.log("[Test] FastAPI exited cleanly.");

    console.log("\n========================================================");
    console.log("  ALL LOCAL SERVICES INTEGRATION TESTS PASSED (100%)");
    console.log("========================================================\n");

    setTimeout(() => {
      process.exit(0);
    }, 500);
  } catch (err) {
    console.error("[Test] ERROR:", err);
    try { pyProc.kill(); } catch {}
    process.exit(1);
  }
}

run();
