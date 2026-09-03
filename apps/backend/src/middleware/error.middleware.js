import { ZodError } from "zod";
import { AppError } from "../utils/errors.js";

/**
 * 404 Not Found handler for unmatched routes
 */
export function notFoundHandler(req, res, next) {
  return res.status(404).json({
    success: false,
    message: `Cannot ${req.method} ${req.originalUrl}`,
  });
}

/**
 * Centralized error handling middleware
 */
export function errorHandler(err, req, res, next) {
  // Handle Zod validation errors
  if (err instanceof ZodError) {
    const errorMessages = err.issues?.map((issue) => {
      const fieldPath = issue.path.join(".");
      return fieldPath ? `${fieldPath}: ${issue.message}` : issue.message;
    });

    return res.status(400).json({
      success: false,
      message: errorMessages?.length ? errorMessages.join("; ") : "Validation failed",
      ...(process.env.NODE_ENV !== "production" ? { details: err.issues } : {}),
    });
  }

  // Handle known operational application errors
  if (err instanceof AppError) {
    return res.status(err.statusCode).json({
      success: false,
      message: err.message,
    });
  }

  // Handle unexpected internal errors
  const isProd = process.env.NODE_ENV === "production";

  if (!isProd) {
    console.error("[Internal Error]", err);
  } else {
    // In production, log a minimal sanitized message without dumping sensitive info
    console.error(`[Internal Error] [${new Date().toISOString()}] ${err.name || "Error"}: ${err.message}`);
  }

  return res.status(500).json({
    success: false,
    message: isProd ? "Internal server error" : (err.message || "Internal server error"),
  });
}
