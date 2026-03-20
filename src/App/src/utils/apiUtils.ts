/**
 * Production-grade API utilities: retry with exponential back-off,
 * request-level caching / deduplication, throttle, and debounce.
 *
 * Also includes the error-parsing helpers extracted from the
 * former `configs/Utils.tsx`.
 *
 * `tryGetRaiPrettyError` is an **internal** helper (not exported).
 */

// ──────────────────────────────────────────────
//  Error-response factory
// ──────────────────────────────────────────────

/**
 * Build a lightweight `Response` object that signals failure.
 * Replaces the `{ ...new Response(), ok: false, status: 500 } as Response`
 * pattern that was previously duplicated across every catch block.
 */
export function createErrorResponse(
  status = 500,
  statusText = "Internal Server Error"
): Response {
  return new Response(null, { status, statusText });
}

// ──────────────────────────────────────────────
//  Retry with exponential back-off
// ──────────────────────────────────────────────

export interface RetryOptions {
  /** Maximum number of retries (default: 3). */
  retries?: number;
  /** Initial delay in ms before the first retry (default: 500). */
  baseDelay?: number;
  /** Multiplier applied to the delay on each retry (default: 2). */
  factor?: number;
  /** Optional predicate – return `true` to retry on this error. */
  shouldRetry?: (error: unknown, attempt: number) => boolean;
}

/**
 * Execute `fn` and, on failure, retry up to `retries` times using
 * exponential back-off with optional jitter.
 *
 * ```ts
 * const data = await retryRequest(() => httpClient.get("/items"), {
 *   retries: 3,
 *   baseDelay: 500,
 * });
 * ```
 */
export async function retryRequest<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    retries = 3,
    baseDelay = 500,
    factor = 2,
    shouldRetry = () => true,
  } = options;

  let lastError: unknown;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt === retries || !shouldRetry(error, attempt)) break;

      // Exponential delay + small random jitter (0 – 20 % of delay)
      const delay = baseDelay * Math.pow(factor, attempt);
      const jitter = delay * 0.2 * Math.random();
      await new Promise((r) => setTimeout(r, delay + jitter));
    }
  }

  throw lastError;
}

// ──────────────────────────────────────────────
//  Request cache / deduplication
// ──────────────────────────────────────────────

interface CacheEntry<T> {
  value: T;
  expiresAt: number;
}

/**
 * In-memory, TTL-based request cache that also prevents duplicate
 * in-flight requests for the same key (request deduplication).
 *
 * ```ts
 * const cache = new RequestCache<ResponseType>(30_000); // 30 s TTL
 *
 * const data = await cache.get("user-list", () => httpClient.get("/users"));
 * ```
 */
export class RequestCache<T = unknown> {
  private cache = new Map<string, CacheEntry<T>>();
  private inflight = new Map<string, Promise<T>>();

  constructor(
    /** Default time-to-live in milliseconds. */
    private ttl: number = 30_000
  ) {}

  /**
   * Retrieve a cached value or execute `factory` to populate it.
   * Concurrent calls with the same `key` while a factory is in-flight
   * will share the same promise (deduplication).
   */
  async get(key: string, factory: () => Promise<T>): Promise<T> {
    // 1. Check the cache
    const cached = this.cache.get(key);
    if (cached && cached.expiresAt > Date.now()) return cached.value;

    // 2. Deduplicate in-flight requests
    const pending = this.inflight.get(key);
    if (pending) return pending;

    // 3. Execute the factory
    const promise = factory().then(
      (value) => {
        this.cache.set(key, { value, expiresAt: Date.now() + this.ttl });
        this.inflight.delete(key);
        return value;
      },
      (err) => {
        this.inflight.delete(key);
        throw err;
      }
    );

    this.inflight.set(key, promise);
    return promise;
  }

  /** Invalidate a single key. */
  invalidate(key: string): void {
    this.cache.delete(key);
  }

  /** Clear the entire cache. */
  clear(): void {
    this.cache.clear();
    this.inflight.clear();
  }
}

// ──────────────────────────────────────────────
//  Throttle
// ──────────────────────────────────────────────

/**
 * Returns a "throttled" version of `fn` that fires at most once
 * every `limit` milliseconds.  Trailing invocations are guaranteed.
 */
export function throttle<T extends (...args: any[]) => any>(
  fn: T,
  limit: number
): (...args: Parameters<T>) => void {
  let lastRun = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;

  return (...args: Parameters<T>) => {
    const now = Date.now();

    if (now - lastRun >= limit) {
      lastRun = now;
      fn(...args);
    } else {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        lastRun = Date.now();
        fn(...args);
      }, limit - (now - lastRun));
    }
  };
}

// ──────────────────────────────────────────────
//  Debounce
// ──────────────────────────────────────────────

/**
 * Returns a "debounced" version of `fn` that delays invocation
 * until `delay` ms have elapsed since the last call.
 */
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null;

  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// ──────────────────────────────────────────────
//  RAI error parsing (internal helper)
// ──────────────────────────────────────────────

/**
 * Attempt to extract a human-readable error from an Azure OpenAI
 * Content Safety / Responsible-AI (RAI) rejection payload.
 * @internal
 */
function tryGetRaiPrettyError(errorMessage: string): string {
  try {
    const match = errorMessage.match(/'innererror': ({.*})\}\}/);
    if (match) {
      const fixedJson = match[1]
        .replace(/'/g, '"')
        .replace(/\bTrue\b/g, "true")
        .replace(/\bFalse\b/g, "false");

      const innerErrorJson = JSON.parse(fixedJson);
      let reason = "";

      const jailbreak = innerErrorJson.content_filter_result.jailbreak;
      if (jailbreak.filtered === true) reason = "Jailbreak";

      if (reason !== "") {
        return (
          "The prompt was filtered due to triggering Azure OpenAI\u2019s content filtering system.\n" +
          "Reason: This prompt contains content flagged as " +
          reason +
          "\n\n" +
          "Please modify your prompt and retry. Learn more: https://go.microsoft.com/fwlink/?linkid=2198766"
        );
      }
    }
  } catch (e) {
    console.error("Failed to parse the error:", e);
  }
  return errorMessage;
}

// ──────────────────────────────────────────────
//  Public error parser
// ──────────────────────────────────────────────

/**
 * Parse a raw error string, extracting inner-error details and
 * delegating to the RAI prettifier when applicable.
 */
export const parseErrorMessage = (errorMessage: string): string => {
  let errorCodeMessage = errorMessage.substring(
    0,
    errorMessage.indexOf("-") + 1
  );
  const innerErrorCue = "{\\'error\\': {\\'message\\': ";

  if (errorMessage.includes(innerErrorCue)) {
    try {
      let innerErrorString = errorMessage.substring(
        errorMessage.indexOf(innerErrorCue)
      );
      if (innerErrorString.endsWith("'}}")) {
        innerErrorString = innerErrorString.substring(
          0,
          innerErrorString.length - 3
        );
      }
      innerErrorString = innerErrorString.replaceAll("\\'", "'");
      errorMessage = errorCodeMessage + " " + innerErrorString;
    } catch (e) {
      console.error("Error parsing inner error message: ", e);
    }
  }

  return tryGetRaiPrettyError(errorMessage);
};
