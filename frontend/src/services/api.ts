import { apiUrl } from "../api";
import { clearTokens, getRefreshToken, setTokens, getAccessToken } from "../utils/tokens";

export class ApiError extends Error {
  status: number;
  detail: string;
  fields: Record<string, unknown>;

  constructor(
    status: number,
    detail: string,
    fields: Record<string, unknown> = {},
  ) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.fields = fields;

    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

async function createApiError(response: Response): Promise<ApiError> {
  try {
    const result = await response.json();

    if (
      result &&
      typeof result === "object" &&
      typeof result.detail === "string"
    ) {
      return new ApiError(response.status, result.detail, result);
    }

    const envelope = result?.error;

    if (
      envelope &&
      typeof envelope === "object" &&
      typeof envelope.message === "string"
    ) {
      return new ApiError(response.status, envelope.message, result);
    }

    if (result && typeof result === "object") {
      for (const value of Object.values(result)) {
        if (Array.isArray(value) && typeof value[0] === "string") {
          return new ApiError(response.status, value[0], result);
        }

        if (typeof value === "string") {
          return new ApiError(response.status, value, result);
        }
      }
    }
  } catch {
    // Fall through to the generic error.
  }

  return new ApiError(
    response.status,
    "An unexpected error occurred.",
  );
}

function handleServerError() {
  window.location.href = "/500";
}

function logout() {
  clearTokens();
  window.location.href = "/auth";
}

function send(
  input: RequestInfo | URL,
  init: RequestInit,
  token: string | null,
): Promise<Response> {
  const headers = new Headers(init.headers);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(apiUrl(input), { ...init, headers });
}

async function ensureOk(response: Response): Promise<Response> {
  if (response.status === 500) {
    handleServerError();
    throw await createApiError(response);
  }

  if (!response.ok) {
    throw await createApiError(response);
  }

  return response;
}

async function requestNewAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();

  if (!refreshToken) return null;

  const response = await fetch(apiUrl("/api/auth/token/refresh/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      refresh: refreshToken,
    }),
  });

  if (!response.ok) {
    if (response.status === 500) {
      handleServerError();
    } else {
      logout();
    }

    throw await createApiError(response);
  }

  const tokens = await response.json();

  setTokens(tokens.access, tokens.refresh);

  return tokens.access;
}

let refreshInFlight: Promise<string | null> | null = null;

function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = requestNewAccessToken().finally(() => {
      refreshInFlight = null;
    });
  }

  return refreshInFlight;
}

export async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const usedToken = getAccessToken();
  const response = await send(input, init, usedToken);

  if (response.status !== 401) {
    return ensureOk(response);
  }

  const currentToken = getAccessToken();
  const token =
    currentToken && currentToken !== usedToken
      ? currentToken
      : await refreshAccessToken();

  if (!token) {
    logout();
    throw await createApiError(response);
  }

  const retryResponse = await send(input, init, token);

  if (retryResponse.status === 401) {
    logout();
    throw await createApiError(retryResponse);
  }

  return ensureOk(retryResponse);
}