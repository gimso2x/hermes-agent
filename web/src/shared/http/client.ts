import { HTTP_CONFIG } from "./config";
import type { HttpError, HttpErrorPayload, HttpRequestOptions } from "./types";

const ABSOLUTE_URL_REGEX = /^https?:\/\//i;

const mergeHeaders = (headers?: HeadersInit): Headers => {
  const merged = new Headers(HTTP_CONFIG.defaultHeaders);

  if (headers) {
    new Headers(headers).forEach((value, key) => {
      merged.set(key, value);
    });
  }

  return merged;
};

const resolveUrl = (path: string): string => {
  if (!path) {
    return HTTP_CONFIG.baseURL;
  }

  if (ABSOLUTE_URL_REGEX.test(path)) {
    return path;
  }

  return `${HTTP_CONFIG.baseURL}${path}`;
};

const createAbortSignal = (timeout: number, signal?: AbortSignal | null) => {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeout);

  if (signal) {
    if (signal.aborted) {
      controller.abort(signal.reason);
    } else {
      signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
    }
  }

  return {
    clear: () => globalThis.clearTimeout(timeoutId),
    signal: controller.signal,
  };
};

const toHttpError = async (response: Response): Promise<HttpError> => {
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await response.json().catch(() => null) : await response.text().catch(() => null);
  const payload =
    data && typeof data === "object"
      ? (data as HttpErrorPayload)
      : undefined;
  const message = payload?.message || response.statusText || `HTTP ${response.status}`;
  const error = new Error(message) as HttpError;

  error.data = data;
  error.payload = payload;
  error.status = response.status;

  return error;
};

export const request = async (path: string, options: HttpRequestOptions = {}): Promise<Response> => {
  const { headers, signal, timeout = HTTP_CONFIG.timeout, ...init } = options;
  const abort = createAbortSignal(timeout, signal);

  try {
    const response = await fetch(resolveUrl(path), {
      ...init,
      headers: mergeHeaders(headers),
      signal: abort.signal,
    });

    if (!response.ok) {
      throw await toHttpError(response);
    }

    return response;
  } finally {
    abort.clear();
  }
};

export const requestJSON = async <T>(path: string, options: HttpRequestOptions = {}): Promise<T> => {
  const response = await request(path, options);
  return (await response.json()) as T;
};

export const requestText = async (path: string, options: HttpRequestOptions = {}): Promise<string> => {
  const response = await request(path, options);
  return response.text();
};

export const httpClient = {
  request,
  requestJSON,
  requestText,
};
