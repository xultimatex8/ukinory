
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { downloadBlob } from "../utils/download";
import { apiFetch } from "./api";
import {
  checkLibraryData,
  exportWatchlistCsv,
  getLibraryStats,
  rateMovie,
  type LibraryStats,
  type RateMoviePayload,
} from "./library";

vi.mock("./api", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("../utils/download", () => ({
  downloadBlob: vi.fn(),
}));

const mockedApiFetch = vi.mocked(apiFetch);
const mockedDownloadBlob = vi.mocked(downloadBlob);

function mockJsonResponse(data: unknown): Response {
  return {
    json: vi.fn().mockResolvedValue(data),
  } as unknown as Response;
}

function mockBlobResponse(blob: Blob): Response {
  return {
    blob: vi.fn().mockResolvedValue(blob),
  } as unknown as Response;
}

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("checkLibraryData", () => {
  it("returns true when the user has film data", async () => {
    mockedApiFetch.mockResolvedValue(mockJsonResponse(true));

    await expect(checkLibraryData()).resolves.toBe(true);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/library/has-film-data/",
      { method: "GET" },
    );
    expect(mockedApiFetch).toHaveBeenCalledTimes(1);
  });

  it("returns false when the user has no film data", async () => {
    mockedApiFetch.mockResolvedValue(mockJsonResponse(false));

    await expect(checkLibraryData()).resolves.toBe(false);
  });

  it("propagates errors from apiFetch", async () => {
    const error = new Error("Request failed");
    mockedApiFetch.mockRejectedValue(error);

    await expect(checkLibraryData()).rejects.toBe(error);
  });
});

describe("getLibraryStats", () => {
  it("returns the library statistics", async () => {
    const stats: LibraryStats = {
      rated_total: 120,
      rated_with_embedding: 95,
    };

    mockedApiFetch.mockResolvedValue(mockJsonResponse(stats));

    await expect(getLibraryStats()).resolves.toEqual(stats);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/library/stats/",
      { method: "GET" },
    );
    expect(mockedApiFetch).toHaveBeenCalledTimes(1);
  });

  it("returns zero counts when the library is empty", async () => {
    const stats: LibraryStats = {
      rated_total: 0,
      rated_with_embedding: 0,
    };

    mockedApiFetch.mockResolvedValue(mockJsonResponse(stats));

    await expect(getLibraryStats()).resolves.toEqual(stats);
  });

  it("propagates errors from apiFetch", async () => {
    const error = new Error("Unable to load library statistics");
    mockedApiFetch.mockRejectedValue(error);

    await expect(getLibraryStats()).rejects.toBe(error);
  });
});

describe("rateMovie", () => {
  it("sends the movie rating as a JSON POST request", async () => {
    const payload: RateMoviePayload = {
      rating: 4.5,
      liked: true,
      watched_date: "2026-05-10",
    };

    mockedApiFetch.mockResolvedValue({} as Response);

    await expect(rateMovie(42, payload)).resolves.toBeUndefined();

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/library/movies/42/rating/",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      },
    );
    expect(mockedApiFetch).toHaveBeenCalledTimes(1);
  });

  it("supports null rating and watched date", async () => {
    const payload: RateMoviePayload = {
      rating: null,
      liked: false,
      watched_date: null,
    };

    mockedApiFetch.mockResolvedValue({} as Response);

    await rateMovie(7, payload);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/library/movies/7/rating/",
      expect.objectContaining({
        body: JSON.stringify(payload),
      }),
    );
  });

  it("supports partial rating payloads", async () => {
    const payload: RateMoviePayload = {
      liked: true,
    };

    mockedApiFetch.mockResolvedValue({} as Response);

    await rateMovie(100, payload);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/library/movies/100/rating/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("propagates errors from apiFetch", async () => {
    const error = new Error("Rating request failed");
    mockedApiFetch.mockRejectedValue(error);

    await expect(
      rateMovie(42, { rating: 3 }),
    ).rejects.toBe(error);
  });
});

describe("exportWatchlistCsv", () => {
  it("downloads the watchlist as a CSV file", async () => {
    const blob = new Blob(["title,rating\nExample,5"], {
      type: "text/csv",
    });

    mockedApiFetch.mockResolvedValue(mockBlobResponse(blob));

    await expect(exportWatchlistCsv()).resolves.toBeUndefined();

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/library/watchlist/export/",
      { method: "GET" },
    );
    expect(mockedDownloadBlob).toHaveBeenCalledWith(
      blob,
      "ukinory_full_watchlist.csv",
    );
    expect(mockedDownloadBlob).toHaveBeenCalledTimes(1);
  });

  it("downloads an empty CSV when the response body is empty", async () => {
    const blob = new Blob([], { type: "text/csv" });

    mockedApiFetch.mockResolvedValue(mockBlobResponse(blob));

    await exportWatchlistCsv();

    expect(mockedDownloadBlob).toHaveBeenCalledWith(
      blob,
      "ukinory_full_watchlist.csv",
    );
  });

  it("propagates errors from apiFetch", async () => {
    const error = new Error("Export failed");
    mockedApiFetch.mockRejectedValue(error);

    await expect(exportWatchlistCsv()).rejects.toBe(error);
    expect(mockedDownloadBlob).not.toHaveBeenCalled();
  });

  it("propagates errors when reading the response blob", async () => {
    const error = new Error("Unable to read CSV response");

    mockedApiFetch.mockResolvedValue({
      blob: vi.fn().mockRejectedValue(error),
    } as unknown as Response);

    await expect(exportWatchlistCsv()).rejects.toBe(error);
    expect(mockedDownloadBlob).not.toHaveBeenCalled();
  });
});