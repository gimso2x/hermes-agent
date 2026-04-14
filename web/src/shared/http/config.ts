export const HTTP_CONFIG = {
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "",
  defaultHeaders: {
    "Content-Type": "application/json",
  },
  timeout: 10000,
} as const;
