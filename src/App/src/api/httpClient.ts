type QueryValue = string | number | boolean | null | undefined;
type QueryParams = Record<string, QueryValue | QueryValue[]>;

export type HttpRequestConfig = {
  url: string;
  method?: string;
  headers?: HeadersInit;
  params?: QueryParams;
  body?: unknown;
  signal?: AbortSignal;
  timeout?: number;
};

type RequestInterceptor =
  | ((config: HttpRequestConfig) => HttpRequestConfig)
  | ((config: HttpRequestConfig) => Promise<HttpRequestConfig>);
type ResponseInterceptor =
  | ((response: Response) => Response)
  | ((response: Response) => Promise<Response>);
type ErrorInterceptor = (error: unknown) => never;

class HttpClient {
  private readonly baseURL = process.env.REACT_APP_API_BASE_URL ?? "";
  private readonly defaultTimeout = 30000;
  private readonly requestInterceptors: RequestInterceptor[] = [];
  private readonly responseInterceptors: ResponseInterceptor[] = [];
  private readonly errorInterceptors: ErrorInterceptor[] = [];

  constructor() {
    this.addRequestInterceptor((config) => {
      const headers = new Headers(config.headers ?? {});
      const userId = localStorage.getItem("userId") ?? "";

      if (!headers.has("Content-Type") && !(config.body instanceof FormData)) {
        headers.set("Content-Type", "application/json");
      }

      if (userId && !headers.has("X-Ms-Client-Principal-Id")) {
        headers.set("X-Ms-Client-Principal-Id", userId);
      }

      return {
        ...config,
        headers,
      };
    });

    this.addResponseInterceptor((response) => {
      if (response.status === 401) {
        throw new Error("Unauthorized request. Sign in and try again.");
      }

      return response;
    });

    this.addErrorInterceptor((error) => {
      throw error instanceof Error
        ? error
        : new Error("Network request failed.");
    });
  }

  addRequestInterceptor(interceptor: RequestInterceptor) {
    this.requestInterceptors.push(interceptor);
  }

  addResponseInterceptor(interceptor: ResponseInterceptor) {
    this.responseInterceptors.push(interceptor);
  }

  addErrorInterceptor(interceptor: ErrorInterceptor) {
    this.errorInterceptors.push(interceptor);
  }

  async request(config: HttpRequestConfig): Promise<Response> {
    const resolvedConfig = await this.runRequestInterceptors(config);
    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(),
      resolvedConfig.timeout ?? this.defaultTimeout
    );

    const abortHandler = () => controller.abort(resolvedConfig.signal?.reason);
    if (resolvedConfig.signal?.aborted) {
      controller.abort(resolvedConfig.signal.reason);
    }
    resolvedConfig.signal?.addEventListener("abort", abortHandler, {
      once: true,
    });

    try {
      const response = await fetch(this.buildUrl(resolvedConfig.url, resolvedConfig.params), {
        method: resolvedConfig.method ?? "GET",
        headers: resolvedConfig.headers,
        body: this.serializeBody(resolvedConfig.body),
        signal: controller.signal,
      });

      return await this.runResponseInterceptors(response);
    } catch (error) {
      return this.runErrorInterceptors(error);
    } finally {
      clearTimeout(timeoutId);
      resolvedConfig.signal?.removeEventListener("abort", abortHandler);
    }
  }

  get(url: string, options: Omit<HttpRequestConfig, "url" | "method" | "body"> = {}) {
    return this.request({
      ...options,
      url,
      method: "GET",
    });
  }

  post(
    url: string,
    body?: unknown,
    options: Omit<HttpRequestConfig, "url" | "method" | "body"> = {}
  ) {
    return this.request({
      ...options,
      url,
      method: "POST",
      body,
    });
  }

  delete(
    url: string,
    body?: unknown,
    options: Omit<HttpRequestConfig, "url" | "method" | "body"> = {}
  ) {
    return this.request({
      ...options,
      url,
      method: "DELETE",
      body,
    });
  }

  private async runRequestInterceptors(config: HttpRequestConfig) {
    let nextConfig = config;

    for (const interceptor of this.requestInterceptors) {
      nextConfig = await interceptor(nextConfig);
    }

    return nextConfig;
  }

  private async runResponseInterceptors(response: Response) {
    let nextResponse = response;

    for (const interceptor of this.responseInterceptors) {
      nextResponse = await interceptor(nextResponse);
    }

    return nextResponse;
  }

  private runErrorInterceptors(error: unknown): never {
    let nextError = error;

    for (const interceptor of this.errorInterceptors) {
      try {
        interceptor(nextError);
      } catch (handledError) {
        nextError = handledError;
      }
    }

    throw nextError instanceof Error
      ? nextError
      : new Error("Network request failed.");
  }

  private buildUrl(url: string, params?: QueryParams) {
    const normalizedUrl = url.startsWith("http")
      ? new URL(url)
      : new URL(`${this.baseURL}${url}`, window.location.origin);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value === undefined || value === null) {
          return;
        }

        if (Array.isArray(value)) {
          value.forEach((item) => {
            if (item !== undefined && item !== null) {
              normalizedUrl.searchParams.append(key, String(item));
            }
          });
          return;
        }

        normalizedUrl.searchParams.set(key, String(value));
      });
    }

    return normalizedUrl.toString();
  }

  private serializeBody(body: unknown): BodyInit | undefined {
    if (body === undefined || body === null) {
      return undefined;
    }

    if (
      typeof body === "string" ||
      body instanceof FormData ||
      body instanceof URLSearchParams ||
      body instanceof Blob
    ) {
      return body;
    }

    return JSON.stringify(body);
  }
}

const httpClient = new HttpClient();

export default httpClient;
