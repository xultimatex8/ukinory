
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiUrl } from "../api";
import { getCurrentLegalDocuments } from "./legal";

vi.mock("../api", () => ({
  apiUrl: vi.fn((path: string) => `http://localhost${path}`),
}));

const mockedApiUrl = vi.mocked(apiUrl);

const legalDocuments = [
  {
    id: 1,
    type: "TERMS",
    version: "1.0",
    content: "Terms and conditions",
    effective_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "privacy-v2",
    type: "PRIVACY",
    version: "2.0",
    content: "Privacy policy",
    effective_at: "2026-02-01T00:00:00Z",
  },
];

function mockResponse(
  body: unknown,
  options: { ok?: boolean; status?: number } = {},
): Response {
  return {
    ok: options.ok ?? true,
    status: options.status ?? 200,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  vi.resetAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("getCurrentLegalDocuments", () => {
  it("fetches and returns the current legal documents", async () => {
    vi.mocked(fetch).mockResolvedValue(mockResponse(legalDocuments));

    await expect(getCurrentLegalDocuments()).resolves.toEqual(legalDocuments);

    expect(mockedApiUrl).toHaveBeenCalledWith("/api/legal/documents/");
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost/api/legal/documents/",
    );
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("returns an empty array when there are no legal documents", async () => {
    vi.mocked(fetch).mockResolvedValue(mockResponse([]));

    await expect(getCurrentLegalDocuments()).resolves.toEqual([]);
  });

  it("throws the response body when the HTTP request fails", async () => {
    const errorBody = {
      detail: "Unable to retrieve legal documents",
    };

    vi.mocked(fetch).mockResolvedValue(
      mockResponse(errorBody, { ok: false, status: 500 }),
    );

    await expect(getCurrentLegalDocuments()).rejects.toEqual(errorBody);
  });

  it("throws the response body for a client error", async () => {
    const errorBody = {
      detail: "Authentication required",
    };

    vi.mocked(fetch).mockResolvedValue(
      mockResponse(errorBody, { ok: false, status: 401 }),
    );

    await expect(getCurrentLegalDocuments()).rejects.toEqual(errorBody);
  });

  it("propagates errors from fetch", async () => {
    const error = new Error("Network error");
    vi.mocked(fetch).mockRejectedValue(error);

    await expect(getCurrentLegalDocuments()).rejects.toBe(error);
  });

  it("propagates errors when parsing the response JSON", async () => {
    const error = new Error("Invalid JSON");

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: vi.fn().mockRejectedValue(error),
    } as unknown as Response);

    await expect(getCurrentLegalDocuments()).rejects.toBe(error);
  });

  it("throws the parsed body even when the error response contains null", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockResponse(null, { ok: false, status: 404 }),
    );

    await expect(getCurrentLegalDocuments()).rejects.toBeNull();
  });
});