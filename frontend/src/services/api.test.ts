import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiUrl } from "../api";
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "../utils/tokens";
import { ApiError, apiFetch } from "./api";

vi.mock("../api", () => ({
  apiUrl: vi.fn((input: RequestInfo | URL) => input),
}));

vi.mock("../utils/tokens", () => ({
  clearTokens: vi.fn(),
  getAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
  setTokens: vi.fn(),
}));

function mockResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

function mockFetchResponses(...responses: Response[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async () => {
      const response = responses.shift();

      if (!response) {
        throw new Error("Unexpected fetch call");
      }

      return response;
    }),
  );
}

const mockedGetAccessToken = vi.mocked(getAccessToken);
const mockedGetRefreshToken = vi.mocked(getRefreshToken);
const mockedSetTokens = vi.mocked(setTokens);
const mockedClearTokens = vi.mocked(clearTokens);
const mockedApiUrl = vi.mocked(apiUrl);

beforeEach(() => {
  vi.resetAllMocks();

  mockedGetAccessToken.mockReturnValue("old-access-token");
  mockedGetRefreshToken.mockReturnValue("refresh-token");
  mockedApiUrl.mockImplementation((input) => input);

  vi.stubGlobal("window", {
    location: { href: "/" },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApiError", () => {
  it("stores the status, detail and fields", () => {
    const fields = { email: ["Invalid email"] };
    const error = new ApiError(400, "Validation failed", fields);

    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.name).toBe("ApiError");
    expect(error.message).toBe("Validation failed");
    expect(error.status).toBe(400);
    expect(error.detail).toBe("Validation failed");
    expect(error.fields).toEqual(fields);
  });
});

describe("apiFetch", () => {
  it("sends the access token with the request", async () => {
    const response = mockResponse(200, { result: "success" });
    mockFetchResponses(response);

    await expect(apiFetch("/api/example/")).resolves.toBe(response);

    expect(fetch).toHaveBeenCalledOnce();

    const [url, init] = vi.mocked(fetch).mock.calls[0];

    expect(url).toBe("/api/example/");
    expect(new Headers(init?.headers).get("Authorization")).toBe(
      "Bearer old-access-token",
    );
    expect(mockedApiUrl).toHaveBeenCalledWith("/api/example/");
  });

  it("sends the request without an authorization header when no access token exists", async () => {
    mockedGetAccessToken.mockReturnValue(null);

    const response = mockResponse(200, {});
    mockFetchResponses(response);

    await apiFetch("/api/example/");

    const [, init] = vi.mocked(fetch).mock.calls[0];

    expect(new Headers(init?.headers).has("Authorization")).toBe(false);
  });

  it("throws ApiError when the server returns a detail error", async () => {
    mockFetchResponses(
      mockResponse(400, {
        detail: "Invalid request",
        code: "invalid",
      }),
    );

    await expect(apiFetch("/api/example/")).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      detail: "Invalid request",
      fields: {
        detail: "Invalid request",
        code: "invalid",
      },
    });
  });

  it("extracts an error message from an error envelope", async () => {
    mockFetchResponses(
      mockResponse(400, {
        error: { message: "Request rejected" },
      }),
    );

    await expect(apiFetch("/api/example/")).rejects.toMatchObject({
      status: 400,
      detail: "Request rejected",
    });
  });

  it("extracts the first string from a validation error", async () => {
    mockFetchResponses(
      mockResponse(400, {
        email: ["Invalid email address"],
      }),
    );

    await expect(apiFetch("/api/example/")).rejects.toMatchObject({
      status: 400,
      detail: "Invalid email address",
    });
  });

  it("uses a generic message when the error response cannot be parsed", async () => {
    const response = {
      status: 400,
      ok: false,
      json: vi.fn().mockRejectedValue(new Error("Invalid JSON")),
    } as unknown as Response;

    mockFetchResponses(response);

    await expect(apiFetch("/api/example/")).rejects.toMatchObject({
      status: 400,
      detail: "An unexpected error occurred.",
    });
  });

  it("redirects to the server error page on HTTP 500", async () => {
    mockFetchResponses(
      mockResponse(500, { detail: "Internal server error" }),
    );

    await expect(apiFetch("/api/example/")).rejects.toMatchObject({
      status: 500,
      detail: "Internal server error",
    });

    expect(window.location.href).toBe("/500");
  });

  it("refreshes the access token and retries after HTTP 401", async () => {
    const refreshedResponse = mockResponse(200, {
      access: "new-access-token",
      refresh: "new-refresh-token",
    });
    const successResponse = mockResponse(200, { result: "success" });

    mockFetchResponses(
      mockResponse(401, { detail: "Token expired" }),
      refreshedResponse,
      successResponse,
    );

    await expect(apiFetch("/api/example/")).resolves.toBe(successResponse);

    expect(fetch).toHaveBeenCalledTimes(3);
    expect(mockedApiUrl).toHaveBeenCalledWith(
      "/api/auth/token/refresh/",
    );
    expect(mockedSetTokens).toHaveBeenCalledWith(
      "new-access-token",
      "new-refresh-token",
    );

    const [retryUrl, retryInit] = vi.mocked(fetch).mock.calls[2];

    expect(retryUrl).toBe("/api/example/");
    expect(
      new Headers(retryInit?.headers).get("Authorization"),
    ).toBe("Bearer new-access-token");
  });

  it("redirects to the server error page when token refresh returns HTTP 500", async () => {
    const initialResponse = mockResponse(401, {
      detail: "Token expired",
    });
    const refreshResponse = mockResponse(500, {
      detail: "Refresh server error",
    });

    mockFetchResponses(initialResponse, refreshResponse);

    await expect(apiFetch("/api/example/")).rejects.toMatchObject({
      status: 500,
      detail: "Refresh server error",
    });

    expect(fetch).toHaveBeenCalledTimes(2);
    expect(mockedApiUrl).toHaveBeenCalledWith(
      "/api/auth/token/refresh/",
    );
    expect(window.location.href).toBe("/500");
    expect(mockedClearTokens).not.toHaveBeenCalled();
  });

  it("logs out when no refresh token is available", async () => {
    mockedGetRefreshToken.mockReturnValue(null);

    mockFetchResponses(
      mockResponse(401, { detail: "Authentication required" }),
    );

    await expect(apiFetch("/api/example/")).rejects.toMatchObject({
      status: 401,
      detail: "Authentication required",
    });

    expect(mockedClearTokens).toHaveBeenCalledOnce();
    expect(window.location.href).toBe("/auth");
    expect(fetch).toHaveBeenCalledOnce();
  });

  it("logs out when refreshing the token fails", async () => {
    mockFetchResponses(
      mockResponse(401, { detail: "Token expired" }),
      mockResponse(401, { detail: "Refresh token expired" }),
    );

    await expect(apiFetch("/api/example/")).rejects.toMatchObject({
      status: 401,
      detail: "Refresh token expired",
    });

    expect(mockedClearTokens).toHaveBeenCalledOnce();
    expect(window.location.href).toBe("/auth");
  });

  it("logs out when the retried request returns HTTP 401", async () => {
    mockFetchResponses(
      mockResponse(401, { detail: "Token expired" }),
      mockResponse(200, {
        access: "new-access-token",
        refresh: "new-refresh-token",
      }),
      mockResponse(401, { detail: "Authentication rejected" }),
    );

    await expect(apiFetch("/api/example/")).rejects.toMatchObject({
      status: 401,
      detail: "Authentication rejected",
    });

    expect(mockedClearTokens).toHaveBeenCalledOnce();
    expect(window.location.href).toBe("/auth");
  });

  it("reuses the updated access token without refreshing it again", async () => {
    const successResponse = mockResponse(200, {
      result: "success",
    });

    mockedGetAccessToken
      .mockReturnValueOnce("old-access-token")
      .mockReturnValueOnce("new-access-token");

    mockFetchResponses(
      mockResponse(401, { detail: "Token expired" }),
      successResponse,
    );

    await expect(apiFetch("/api/example/")).resolves.toBe(successResponse);

    expect(fetch).toHaveBeenCalledTimes(2);
    expect(mockedGetRefreshToken).not.toHaveBeenCalled();

    const [, retryInit] = vi.mocked(fetch).mock.calls[1];

    expect(
      new Headers(retryInit?.headers).get("Authorization"),
    ).toBe("Bearer new-access-token");
  });

  it("preserves the original request body when retrying", async () => {
    const requestInit: RequestInit = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Example" }),
    };

    mockFetchResponses(
      mockResponse(401, { detail: "Token expired" }),
      mockResponse(200, {
        access: "new-access-token",
        refresh: "new-refresh-token",
      }),
      mockResponse(201, { id: 1 }),
    );

    await apiFetch("/api/example/", requestInit);

    const [, retryInit] = vi.mocked(fetch).mock.calls[2];

    expect(retryInit?.method).toBe("POST");
    expect(retryInit?.body).toBe(requestInit.body);
    expect(
      new Headers(retryInit?.headers).get("Authorization"),
    ).toBe("Bearer new-access-token");
  });
});