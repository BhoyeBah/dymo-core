import type { ApiErrorShape } from "@/types";
import { clearSession, getBearerToken, getTenantSlug } from "@/lib/auth";

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

export class ApiError extends Error implements ApiErrorShape {
  status: number;
  code?: string | undefined;
  details?: unknown;

  constructor(payload: ApiErrorShape) {
    super(payload.message);
    this.name = "ApiError";
    this.status = payload.status;
    this.code = payload.code;
    this.details = payload.details;
  }
}

function getBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_BASE_URL;
}

function buildUrl(path: string) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  return `${getBaseUrl().replace(/\/$/, "")}${path}`;
}

function parseError(status: number, payload: unknown): ApiError {
  if (typeof payload === "object" && payload !== null) {
    const candidate = payload as Record<string, unknown>;
    const message =
      typeof candidate.detail === "string"
        ? candidate.detail
        : typeof candidate.message === "string"
          ? candidate.message
          : typeof candidate.error === "string"
            ? candidate.error
            : `HTTP ${status}`;

    return new ApiError({
      message,
      status,
      code: typeof candidate.code === "string" ? candidate.code : undefined,
      details: candidate
    });
  }

  return new ApiError({ message: `HTTP ${status}`, status, details: payload });
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  const token = getBearerToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const tenantSlug = getTenantSlug();
  if (tenantSlug) {
    headers.set("X-Tenant-Slug", tenantSlug);
  }

  if (init.body && !headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildUrl(path), {
    ...init,
    headers,
    credentials: "include"
  });

  if (response.status === 401) {
    clearSession();
    throw new ApiError({ message: "Session expirée", status: 401, code: "UNAUTHORIZED" });
  }

  if (response.status === 403) {
    throw new ApiError({ message: "Accès refusé", status: 403, code: "FORBIDDEN" });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    throw parseError(response.status, payload);
  }

  return payload as T;
}

export async function safeApiRequest<T>(
  path: string,
  init: RequestInit = {}
): Promise<{ data: T | null; error: ApiError | null }> {
  try {
    const data = await apiRequest<T>(path, init);
    return { data, error: null };
  } catch (error) {
    return { data: null, error: error instanceof ApiError ? error : new ApiError({ message: "Erreur inconnue", status: 500, details: error }) };
  }
}

