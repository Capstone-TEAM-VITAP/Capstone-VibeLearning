import express from "express";
import cors from "cors";
import { clerkMiddleware } from "@clerk/express";

import authRoutes from "./routes/auth.routes.js";
import projectRoutes from "./routes/project.routes.js";
import repoRoutes from "./routes/repo.routes.js";
import webhookRoutes from "./routes/webhook.routes.js";
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

// Health check (public, before auth)
app.get("/api/v1/health", (req, res) => {
  res.json({
    success: true,
    data: {
      status: "healthy",
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

// Catch-all 404 handler for undefined routes
app.use(notFoundHandler);

// Centralized error handling middleware
app.use(errorHandler);

export default app;
