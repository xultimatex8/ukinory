export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;

    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

async function createApiError(response: Response): Promise<ApiError> {
  let detail = "An unexpected error occurred.";

  try {
    const result = await response.json();
    console.log(result);

    if (
      result &&
      typeof result === "object" &&
      typeof result.detail === "string"
    ) {
      detail = result.detail;
    }
  } catch {
    // Keep the generic message if the response is not valid JSON.
  }

  return new ApiError(response.status, detail);
}

function handleServerError() {
  window.location.href = "/500";
}

export async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const accessToken = localStorage.getItem("access_token");
  const headers = new Headers(init.headers);

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(input, {
    ...init,
    headers,
  });

  if (response.status !== 401) {
    if (response.status === 500) {
      handleServerError();
      throw await createApiError(response);
    }

    if (!response.ok) {
      throw await createApiError(response);
    }

    return response;
  }

  const refreshToken = localStorage.getItem("refresh_token");

  if (!refreshToken) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/auth";

    throw await createApiError(response);
  }

  const refreshResponse = await fetch("/api/auth/token/refresh/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      refresh: refreshToken,
    }),
  });

  if (!refreshResponse.ok) {
    if (refreshResponse.status === 500) {
      handleServerError();
      throw await createApiError(refreshResponse);
    }

    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/auth";

    throw await createApiError(refreshResponse);
  }

  const tokens = await refreshResponse.json();

  localStorage.setItem("access_token", tokens.access);

  if (tokens.refresh) {
    localStorage.setItem("refresh_token", tokens.refresh);
  }

  const retryHeaders = new Headers(init.headers);
  retryHeaders.set("Authorization", `Bearer ${tokens.access}`);

  const retryResponse = await fetch(input, {
    ...init,
    headers: retryHeaders,
  });

  if (retryResponse.status === 401) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/auth";

    throw await createApiError(retryResponse);
  }

  if (retryResponse.status === 500) {
    handleServerError();
    throw await createApiError(retryResponse);
  }

  if (!retryResponse.ok) {
    throw await createApiError(retryResponse);
  }

  return retryResponse;
}