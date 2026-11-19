import express from "express";
import cors from "cors";
import { clerkMiddleware } from "@clerk/express";

import authRoutes from "./routes/auth.routes.js";
import projectRoutes from "./routes/project.routes.js";
import repoRoutes from "./routes/repo.routes.js";
import webhookRoutes from "./routes/webhook.routes.js";
import settingsRoutes from "./routes/settings.routes.js";
import { notFoundHandler, errorHandler } from "./middleware/error.middleware.js";

const app = express();

const defaultOrigins = ["http://localhost:5173"];
const configuredOrigins = process.env.CORS_ORIGINS
  ? process.env.CORS_ORIGINS.split(",").map((origin) => origin.trim()).filter(Boolean)
  : [];
const allowedOrigins = Array.from(new Set([...defaultOrigins, ...configuredOrigins]));

app.use(
  cors({
    origin: (origin, callback) => {
      // Allow requests without an Origin header (Postman, curl, server-to-server)
      if (!origin) {
        return callback(null, true);
      }

      if (allowedOrigins.includes(origin)) {
        return callback(null, true);
      }

      return callback(null, false);
    },
    credentials: true,
  })
);

app.use(
  express.json({
    // Stash exact request bytes for HMAC verification (GitHub webhooks).
    // JSON parsing must not alter them, so capture before parsing.
    verify: (req, res, buf) => {
      req.rawBody = Buffer.from(buf);
    },
  })
);

// Health check (public, before auth) - verifies both Express backend and FastAPI AI service
app.get(["/health", "/api/v1/health"], async (req, res) => {
  const aiServiceUrl = (process.env.AI_SERVICE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
  let aiServiceStatus = "unknown";
  let aiError = null;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2500);
    const aiRes = await fetch(`${aiServiceUrl}/health`, {
      signal: controller.signal,
    }).finally(() => clearTimeout(timer));

    if (aiRes.ok) {
      aiServiceStatus = "ok";
    } else {
      aiServiceStatus = `error (status ${aiRes.status})`;
    }
  } catch (err) {
    aiServiceStatus = "unavailable";
    aiError = err.message || "Connection refused";
  }

  const isHealthy = aiServiceStatus === "ok";
  const statusCode = isHealthy ? 200 : 503;

  return res.status(statusCode).json({
    success: isHealthy,
    data: {
      status: isHealthy ? "healthy" : "degraded",
      services: {
        backend: "ok",
        aiService: aiServiceStatus,
      },
      ...(aiError ? { error: aiError } : {}),
    },
  });
});

// Clerk authentication middleware
app.use(clerkMiddleware());

// API Routes
app.use("/api/v1/auth", authRoutes);
app.use("/api/v1/projects", projectRoutes);
app.use("/api/v1/repos", repoRoutes);
app.use("/api/v1/webhooks", webhookRoutes);
app.use("/api/v1/settings", settingsRoutes);

// Catch-all 404 handler for undefined routes
app.use(notFoundHandler);

// Centralized error handling middleware
app.use(errorHandler);

export default app;
