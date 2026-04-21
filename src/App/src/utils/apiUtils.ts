export const createErrorResponse = (
  status = 500,
  message = "Request failed."
): Response =>
  new Response(JSON.stringify({ error: message }), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });

export async function retryRequest<T>(
  operation: () => Promise<T>,
  retries = 2,
  baseDelayMs = 300
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;

      if (attempt === retries) {
        break;
      }

      await new Promise((resolve) => setTimeout(resolve, baseDelayMs * 2 ** attempt));
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error("Request retry limit exceeded.");
}

export class RequestCache<T> {
  private readonly cache = new Map<string, Promise<T>>();

  getOrCreate(key: string, factory: () => Promise<T>): Promise<T> {
    if (!this.cache.has(key)) {
      this.cache.set(key, factory());
    }

    return this.cache.get(key)!;
  }

  clear(key?: string) {
    if (key) {
      this.cache.delete(key);
      return;
    }

    this.cache.clear();
  }
}

export function debounce<T extends (...args: any[]) => void>(
  callback: T,
  delay: number
) {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      callback(...args);
    }, delay);
  };
}

export function throttle<T extends (...args: any[]) => void>(
  callback: T,
  wait: number
) {
  let isThrottled = false;

  return (...args: Parameters<T>) => {
    if (isThrottled) {
      return;
    }

    callback(...args);
    isThrottled = true;

    setTimeout(() => {
      isThrottled = false;
    }, wait);
  };
}
