import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  addRecommendationToWatchlist,
  exportRecommendationsWatchlist,
  removeRecommendationFromWatchlist,
  type JointRecommendation,
} from "../services/comparisons";
import { downloadBlob } from "../utils/download";
import { getErrorMessage } from "../utils/errors";
import { useRecommendationWatchlist } from "./useRecommendationWatchlist";

vi.mock("../services/comparisons", () => ({
  addRecommendationToWatchlist: vi.fn(),
  exportRecommendationsWatchlist: vi.fn(),
  removeRecommendationFromWatchlist: vi.fn(),
}));

vi.mock("../utils/download", () => ({
  downloadBlob: vi.fn(),
}));

vi.mock("../utils/errors", () => ({
  getErrorMessage: vi.fn(),
}));

const mockedAddRecommendationToWatchlist = vi.mocked(
  addRecommendationToWatchlist,
);
const mockedExportRecommendationsWatchlist = vi.mocked(
  exportRecommendationsWatchlist,
);
const mockedRemoveRecommendationFromWatchlist = vi.mocked(
  removeRecommendationFromWatchlist,
);
const mockedDownloadBlob = vi.mocked(downloadBlob);
const mockedGetErrorMessage = vi.mocked(getErrorMessage);

function makeRecommendation(
  movieId: string | number,
  inWatchlist = false,
): JointRecommendation {
  return {
    movie_id: movieId,
    in_watchlist: inWatchlist,
  } as JointRecommendation;
}

describe("useRecommendationWatchlist", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockedAddRecommendationToWatchlist.mockResolvedValue(undefined);
    mockedRemoveRecommendationFromWatchlist.mockResolvedValue(undefined);
    mockedExportRecommendationsWatchlist.mockResolvedValue(new Blob(["csv"]));
    mockedGetErrorMessage.mockReturnValue("Something went wrong");
  });

  it("initializes saved movies from recommendations in the watchlist", () => {
    const recommendations = [
      makeRecommendation(1, true),
      makeRecommendation("2", false),
      makeRecommendation(3, true),
    ];

    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", recommendations),
    );

    expect(result.current.isSaved(1)).toBe(true);
    expect(result.current.isSaved("3")).toBe(true);
    expect(result.current.isSaved(2)).toBe(false);
    expect(result.current.savedCount).toBe(2);
  });

  it("normalizes numeric and string movie IDs", () => {
    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", [makeRecommendation("42", true)]),
    );

    expect(result.current.isSaved(42)).toBe(true);
    expect(result.current.isSaved("42")).toBe(true);
    expect(result.current.isPending(42)).toBe(false);
  });

  it("adds a movie optimistically and calls the add service", async () => {
    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", []),
    );

    await act(async () => {
      await result.current.toggle(12);
    });

    expect(mockedAddRecommendationToWatchlist).toHaveBeenCalledWith(
      "room-1",
      12,
    );
    expect(result.current.isSaved(12)).toBe(true);
    expect(result.current.savedCount).toBe(1);
    expect(result.current.isPending(12)).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("removes a saved movie and calls the remove service", async () => {
    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", [makeRecommendation("12", true)]),
    );

    await act(async () => {
      await result.current.toggle(12);
    });

    expect(mockedRemoveRecommendationFromWatchlist).toHaveBeenCalledWith(
      "room-1",
      12,
    );
    expect(result.current.isSaved(12)).toBe(false);
    expect(result.current.savedCount).toBe(0);
  });

  it("sets the pending state while adding a movie", async () => {
    let resolveAdd!: () => void;
    mockedAddRecommendationToWatchlist.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveAdd = resolve;
        }),
    );

    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", []),
    );

    let togglePromise!: Promise<void>;
    act(() => {
      togglePromise = result.current.toggle("movie-1");
    });

    expect(result.current.isPending("movie-1")).toBe(true);
    expect(result.current.isSaved("movie-1")).toBe(true);

    await act(async () => {
      resolveAdd();
      await togglePromise;
    });

    expect(result.current.isPending("movie-1")).toBe(false);
  });

  it("does not start another toggle for a movie that is already pending", async () => {
    let resolveAdd!: () => void;
    mockedAddRecommendationToWatchlist.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveAdd = resolve;
        }),
    );

    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", []),
    );

    let firstToggle!: Promise<void>;
    act(() => {
      firstToggle = result.current.toggle("movie-1");
    });

    await waitFor(() => {
      expect(result.current.isPending("movie-1")).toBe(true);
    });

    await act(async () => {
      await result.current.toggle("movie-1");
    });

    expect(mockedAddRecommendationToWatchlist).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveAdd();
      await firstToggle;
    });
  });

  it("rolls back an optimistic add when the service fails", async () => {
    const failure = new Error("Add failed");
    mockedAddRecommendationToWatchlist.mockRejectedValueOnce(failure);
    mockedGetErrorMessage.mockReturnValueOnce("Could not add movie");

    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", []),
    );

    await act(async () => {
      await result.current.toggle("movie-1");
    });

    expect(result.current.isSaved("movie-1")).toBe(false);
    expect(result.current.savedCount).toBe(0);
    expect(result.current.error).toBe("Could not add movie");
    expect(mockedGetErrorMessage).toHaveBeenCalledWith(failure);
    expect(result.current.isPending("movie-1")).toBe(false);
  });

  it("restores a movie when removing it fails", async () => {
    const failure = new Error("Remove failed");
    mockedRemoveRecommendationFromWatchlist.mockRejectedValueOnce(failure);
    mockedGetErrorMessage.mockReturnValueOnce("Could not remove movie");

    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", [makeRecommendation("movie-1", true)]),
    );

    await act(async () => {
      await result.current.toggle("movie-1");
    });

    expect(result.current.isSaved("movie-1")).toBe(true);
    expect(result.current.savedCount).toBe(1);
    expect(result.current.error).toBe("Could not remove movie");
    expect(mockedGetErrorMessage).toHaveBeenCalledWith(failure);
    expect(result.current.isPending("movie-1")).toBe(false);
  });

  it("clears an existing error when toggling a movie", async () => {
    mockedAddRecommendationToWatchlist.mockRejectedValueOnce(new Error("Failed"));

    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", []),
    );

    await act(async () => {
      await result.current.toggle("movie-1");
    });

    expect(result.current.error).toBe("Something went wrong");

    await act(async () => {
      await result.current.toggle("movie-2");
    });

    expect(result.current.error).toBeNull();
  });

  it("exports the watchlist as a CSV file", async () => {
    const blob = new Blob(["movie_id,title\n1,Example"]);
    mockedExportRecommendationsWatchlist.mockResolvedValueOnce(blob);

    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", []),
    );

    await act(async () => {
      await result.current.exportCsv();
    });

    expect(mockedExportRecommendationsWatchlist).toHaveBeenCalledWith("room-1");
    expect(mockedDownloadBlob).toHaveBeenCalledWith(
      blob,
      "ukinory_comparison_watchlist.csv",
    );
    expect(result.current.isExporting).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("sets the exporting state while the CSV export is pending", async () => {
    let resolveExport!: (blob: Blob) => void;
    mockedExportRecommendationsWatchlist.mockImplementation(
      () =>
        new Promise<Blob>((resolve) => {
          resolveExport = resolve;
        }),
    );

    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", []),
    );

    let exportPromise!: Promise<void>;
    act(() => {
      exportPromise = result.current.exportCsv();
    });

    expect(result.current.isExporting).toBe(true);

    await act(async () => {
      resolveExport(new Blob(["csv"]));
      await exportPromise;
    });

    expect(result.current.isExporting).toBe(false);
  });

  it("sets an error when CSV export fails", async () => {
    const failure = new Error("Export failed");
    mockedExportRecommendationsWatchlist.mockRejectedValueOnce(failure);
    mockedGetErrorMessage.mockReturnValueOnce("Could not export watchlist");

    const { result } = renderHook(() =>
      useRecommendationWatchlist("room-1", []),
    );

    await act(async () => {
      await result.current.exportCsv();
    });

    expect(result.current.error).toBe("Could not export watchlist");
    expect(mockedGetErrorMessage).toHaveBeenCalledWith(failure);
    expect(mockedDownloadBlob).not.toHaveBeenCalled();
    expect(result.current.isExporting).toBe(false);
  });
});