import { getAuth } from "@clerk/express";

/**
 * Middleware to require authentication on protected routes.
 * Expects clerkMiddleware() to be registered before this in the Express middleware chain.
 */
export function requireAuth(req, res, next) {
  const { userId } = getAuth(req);

  if (!userId) {
    return res.status(401).json({
      success: false,
      message: "Unauthorized",
    });
  }

  req.userId = userId;
  next();
}
