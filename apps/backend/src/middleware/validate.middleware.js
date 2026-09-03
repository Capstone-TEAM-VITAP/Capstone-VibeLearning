/**
 * Express middleware factory to validate incoming request data using Zod schemas.
 * Supports validating body, params, and query.
 *
 * @param {object} schemas - Object containing { body?, params?, query? } Zod schemas
 */
export function validate(schemas) {
  return async (req, res, next) => {
    try {
      if (schemas.params) {
        req.params = await schemas.params.parseAsync(req.params);
      }
      if (schemas.query) {
        const parsed = await schemas.query.parseAsync(req.query);
        // Express 5 exposes req.query as a prototype getter with no setter,
        // so plain assignment throws. Shadow it with an own property instead.
        Object.defineProperty(req, "query", {
          value: parsed,
          writable: true,
          enumerable: true,
          configurable: true,
        });
      }
      if (schemas.body) {
        req.body = await schemas.body.parseAsync(req.body);
      }
      next();
    } catch (error) {
      next(error);
    }
  };
}
