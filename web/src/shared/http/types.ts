export interface HttpErrorPayload {
  code?: string;
  message?: string;
  status?: number;
}

export interface HttpError extends Error {
  data?: unknown;
  payload?: HttpErrorPayload;
  status: number;
}

export interface HttpRequestOptions extends Omit<RequestInit, "headers"> {
  headers?: HeadersInit;
  timeout?: number;
}
