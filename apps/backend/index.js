import "dotenv/config";
import app from "./src/app.js";

const PORT = Number(process.env.PORT) || 5000;
const HOST = process.env.HOST || "0.0.0.0";

const server = app.listen(PORT, HOST, () => {
  console.log(`[CodeAI Backend] Server listening on ${HOST}:${PORT}`);
});

// Graceful shutdown handling for Cloud Run SIGTERM / SIGINT
function handleShutdown(signal) {
  console.log(`[CodeAI Backend] Received ${signal}. Starting graceful shutdown...`);
  server.close((err) => {
    if (err) {
      console.error("[CodeAI Backend] Error while closing HTTP server:", err);
      process.exit(1);
    }
    console.log("[CodeAI Backend] HTTP server closed cleanly. Exiting.");
    process.exit(0);
  });

  // Force close after 10 seconds if connections are hanging
  setTimeout(() => {
    console.error("[CodeAI Backend] Forced shutdown after timeout.");
    process.exit(1);
  }, 10000).unref();
}

process.on("SIGTERM", () => handleShutdown("SIGTERM"));
process.on("SIGINT", () => handleShutdown("SIGINT"));

export default server;