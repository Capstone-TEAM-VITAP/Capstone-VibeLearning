import "temporal-polyfill/global";

/**
 * Normalize a value for Prisma DateTime (timestamptz-temporal) columns.
 * The ORM codec only accepts Temporal.Instant — plain ISO strings fail
 * with RUNTIME.ENCODE_FAILED. Null/empty stays null (column is nullable).
 */
export function toInstant(value) {
  if (value == null) return null;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return null;
    return Temporal.Instant.from(trimmed);
  }
  return value;
}
