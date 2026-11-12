import catalog from "../../../../services/error_catalog.json";

export const messages = Object.fromEntries(
  Object.entries(catalog.errors).map(([code, entry]) => [code, entry.message]),
) as Record<keyof typeof catalog.errors, string>;

export type ApiErrorCode = keyof typeof catalog.errors;

export function safeErrorCode(value: unknown): ApiErrorCode {
  return typeof value === "string" && Object.hasOwn(catalog.errors, value)
    ? (value as ApiErrorCode)
    : (catalog.fallback as ApiErrorCode);
}

export class ApiError extends Error {
  constructor(public readonly code: ApiErrorCode, public readonly status: number) {
    super(messages[code]);
    this.name = "ApiError";
  }
}
