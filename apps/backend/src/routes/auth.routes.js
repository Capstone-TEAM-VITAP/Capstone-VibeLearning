import express from "express";
import { getAuth } from "@clerk/express";
import { requireAuth } from "../middleware/auth.middleware.js";

const router = express.Router();

router.get("/me", requireAuth, (req, res) => {
  const { userId } = getAuth(req);

  if (!userId) {
    return res.status(401).json({
      success: false,
      message: "Unauthorized",
    });
  }

  return res.json({
    success: true,
    data: {
      userId,
    },
  });
});

export default router;