/**
 * JSON-related utilities.
 *
 * `safeParse` replaces the dozens of bare `try { JSON.parse(…) } catch {}`
 * blocks scattered throughout the codebase (12+ sites in useChatApi alone).
 */

/**
 * Attempt to parse a JSON string and return the parsed value.
 * If parsing fails, return the supplied `fallback` instead of throwing.
 */
export function safeParse<T>(json: string, fallback: T): T {
  try {
    return json ? JSON.parse(json) : fallback;
  } catch {
    return fallback;
  }
}

/**
 * Attempt to serialise a value to JSON.
 * Returns `fallback` on circular-reference or other serialisation errors.
 */
export function safeStringify(
  value: unknown,
  fallback: string = "",
  space?: number
): string {
  try {
    return JSON.stringify(value, null, space) ?? fallback;
  } catch {
    return fallback;
  }
}
