/**
 * Standardized API success response
 */
export function successResponse(res, data = {}, statusCode = 200) {
  return res.status(statusCode).json({
    success: true,
    data,
  });
}

/**
 * Standardized API list response with metadata
 */
export function listResponse(res, data = [], meta = {}, statusCode = 200) {
  return res.status(statusCode).json({
    success: true,
    data,
    meta: {
      total: meta.total ?? data.length,
      ...meta,
    },
  });
}

/**
 * Standardized API error response
 */
export function errorResponse(res, message = "An error occurred", statusCode = 500, errors = undefined) {
  const payload = {
    success: false,
    message,
  };

  if (errors && process.env.NODE_ENV !== "production") {
    payload.errors = errors;
  }

  return res.status(statusCode).json(payload);
}
