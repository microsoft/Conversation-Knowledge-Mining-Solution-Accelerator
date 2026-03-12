/**
 * Singleton HTTP client with request/response interceptors,
 * configurable base URL, timeout, and params serialization.
 *
 * Eliminates duplicated localStorage.getItem("userId") and
 * manual header construction across every API function.
 */

import { retryRequest, type RetryOptions } from "../utils/apiUtils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type QueryParams = Record<
  string,
  string | number | boolean | undefined | null
>;

export interface HttpClientConfig {
  baseURL?: string;
  timeout?: number;
  headers?: Record<string, string>;
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  /** Query-string parameters – serialized automatically. */
  params?: QueryParams;
  /** Timeout in ms – overrides the instance default. */
  timeout?: number;
  /** Convenience property – JSON-serialized as the body. */
  body?: any;
  /**
   * When `true` the raw `Response` is returned without
   * running response-interceptors or JSON-parsing.
   * Useful for streaming endpoints (e.g. `callConversationApi`).
   */
  rawResponse?: boolean;
  /**
   * When provided the request is automatically retried on failure
   * using exponential back-off.  Pass `true` for default retry
   * settings, or a `RetryOptions` object for fine-grained control.
   */
  retry?: boolean | RetryOptions;
}

export type RequestInterceptor = (
  url: string,
  options: RequestInit
) => [string, RequestInit] | Promise<[string, RequestInit]>;

export type ResponseInterceptor = (
  response: Response
) => Response | Promise<Response>;

// ---------------------------------------------------------------------------
// HttpClient
// ---------------------------------------------------------------------------

class HttpClient {
  private baseURL: string;
  private defaultTimeout: number;
  private defaultHeaders: Record<string, string>;
  private requestInterceptors: RequestInterceptor[] = [];
  private responseInterceptors: ResponseInterceptor[] = [];

  constructor(config: HttpClientConfig = {}) {
    this.baseURL = (config.baseURL ?? "").replace(/\/+$/, "");
    this.defaultTimeout = config.timeout ?? 30_000;
    this.defaultHeaders = config.headers ?? {};
  }

  // ---- interceptor registration ------------------------------------------

  addRequestInterceptor(fn: RequestInterceptor): void {
    this.requestInterceptors.push(fn);
  }

  addResponseInterceptor(fn: ResponseInterceptor): void {
    this.responseInterceptors.push(fn);
  }

  // ---- convenience verbs -------------------------------------------------

  get<T = any>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, { ...options, method: "GET" });
  }

  post<T = any>(url: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, { ...options, method: "POST", body });
  }

  put<T = any>(url: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, { ...options, method: "PUT", body });
  }

  patch<T = any>(
    url: string,
    body?: any,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(url, { ...options, method: "PATCH", body });
  }

  delete<T = any>(
    url: string,
    body?: any,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(url, { ...options, method: "DELETE", body });
  }

  // ---- core request -------------------------------------------------------

  async request<T = any>(
    url: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { retry, ...rest } = options;

    // If retry is enabled, wrap the inner request in retryRequest
    if (retry) {
      const retryOpts: RetryOptions =
        typeof retry === "object" ? retry : {};
      return retryRequest(() => this._execute<T>(url, rest), retryOpts);
    }

    return this._execute<T>(url, rest);
  }

  // ---- inner execution (no retry wrapping) --------------------------------

  private async _execute<T = any>(
    url: string,
    options: Omit<RequestOptions, "retry"> = {}
  ): Promise<T> {
    const {
      params,
      timeout,
      body,
      rawResponse,
      headers: extraHeaders,
      ...restInit
    } = options;

    // --- build URL ----------------------------------------------------------
    let fullURL = url.startsWith("http") ? url : `${this.baseURL}${url}`;

    if (params) {
      const qs = this.serializeParams(params);
      if (qs) {
        fullURL += (fullURL.includes("?") ? "&" : "?") + qs;
      }
    }

    // --- build RequestInit ---------------------------------------------------
    const init: RequestInit = {
      ...restInit,
      headers: {
        ...this.defaultHeaders,
        ...(extraHeaders as Record<string, string>),
      },
    };

    if (body !== undefined && body !== null) {
      if (typeof body === "string" || body instanceof FormData) {
        init.body = body as any;
      } else {
        init.body = JSON.stringify(body);
        // Ensure Content-Type for JSON bodies
        (init.headers as Record<string, string>)["Content-Type"] =
          (init.headers as Record<string, string>)["Content-Type"] ??
          "application/json";
      }
    }

    // --- run request interceptors -------------------------------------------
    let interceptedURL = fullURL;
    let interceptedInit = init;
    for (const interceptor of this.requestInterceptors) {
      [interceptedURL, interceptedInit] = await interceptor(
        interceptedURL,
        interceptedInit
      );
    }

    // --- timeout via AbortController ----------------------------------------
    const effectiveTimeout = timeout ?? this.defaultTimeout;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();

    // Merge with any caller-provided signal
    const externalSignal = interceptedInit.signal;
    if (externalSignal) {
      // If the external signal already aborted, forward immediately.
      if (externalSignal.aborted) {
        controller.abort(externalSignal.reason);
      } else {
        externalSignal.addEventListener(
          "abort",
          () => controller.abort(externalSignal.reason),
          { once: true }
        );
      }
    }

    if (effectiveTimeout > 0) {
      timeoutId = setTimeout(
        () => controller.abort(new DOMException("Request timeout", "TimeoutError")),
        effectiveTimeout
      );
    }

    interceptedInit.signal = controller.signal;

    // --- fetch --------------------------------------------------------------
    let response: Response;
    try {
      response = await fetch(interceptedURL, interceptedInit);
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId);
    }

    // --- raw mode (streaming, etc.) -----------------------------------------
    if (rawResponse) {
      return response as unknown as T;
    }

    // --- run response interceptors ------------------------------------------
    for (const interceptor of this.responseInterceptors) {
      response = await interceptor(response);
    }

    // --- parse JSON ---------------------------------------------------------
    const text = await response.text();
    try {
      return text ? JSON.parse(text) : (undefined as unknown as T);
    } catch {
      return text as unknown as T;
    }
  }

  // ---- helpers ------------------------------------------------------------

  private serializeParams(params: QueryParams): string {
    const parts: string[] = [];
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null) continue;
      parts.push(
        `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`
      );
    }
    return parts.join("&");
  }
}

// ---------------------------------------------------------------------------
// Singleton instance + default interceptors
// ---------------------------------------------------------------------------

const httpClient = new HttpClient({
  baseURL: process.env.REACT_APP_API_BASE_URL ?? "",
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor: attach auth header from localStorage
httpClient.addRequestInterceptor((url, init) => {
  const userId = localStorage.getItem("userId");
  if (userId) {
    const headers = init.headers as Record<string, string>;
    headers["X-Ms-Client-Principal-Id"] =
      headers["X-Ms-Client-Principal-Id"] ?? userId;
  }
  return [url, init];
});

// Response interceptor: uniform error logging
httpClient.addResponseInterceptor((response) => {
  if (!response.ok) {
    console.error(
      `HTTP ${response.status} ${response.statusText} – ${response.url}`
    );
  }
  return response;
});

export default httpClient;
