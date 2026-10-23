import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useNavigate } from "react-router-dom";
import { endSwipeSession } from "../services/swipeSessions";
import { downloadBlob } from "../utils/download";
import { getErrorMessage } from "../utils/errors";
import { useEndSwipeSession } from "./useEndSwipeSession";

vi.mock("react-router-dom", () => ({
  useNavigate: vi.fn(),
}));

vi.mock("../services/swipeSessions", () => ({
  endSwipeSession: vi.fn(),
}));

vi.mock("../utils/download", () => ({
  downloadBlob: vi.fn(),
}));

vi.mock("../utils/errors", () => ({
  getErrorMessage: vi.fn(),
}));

const mockedUseNavigate = vi.mocked(useNavigate);
const mockedEndSwipeSession = vi.mocked(endSwipeSession);
const mockedDownloadBlob = vi.mocked(downloadBlob);
const mockedGetErrorMessage = vi.mocked(getErrorMessage);

describe("useEndSwipeSession", () => {
  const navigate = vi.fn();
  const csvBlob = new Blob(["title,year\nExample,2025"], {
    type: "text/csv",
  });

  beforeEach(() => {
    vi.clearAllMocks();

    mockedUseNavigate.mockReturnValue(navigate);
    mockedEndSwipeSession.mockResolvedValue(csvBlob);
    mockedGetErrorMessage.mockReturnValue("Something went wrong");
  });

  it("returns the initial state and handlers", () => {
    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    expect(result.current.isEndingSession).toBe(false);
    expect(result.current.endSessionError).toBeNull();
    expect(result.current.clearEndSessionError).toEqual(expect.any(Function));
    expect(result.current.handleGoHome).toEqual(expect.any(Function));
    expect(result.current.handleDownloadCsv).toEqual(expect.any(Function));
  });

  it("ends the session and navigates home when handleGoHome is called", async () => {
    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleGoHome();
    });

    await waitFor(() => {
      expect(mockedEndSwipeSession).toHaveBeenCalledWith("session-123");
      expect(navigate).toHaveBeenCalledWith("/");
    });

    expect(mockedDownloadBlob).not.toHaveBeenCalled();
    expect(result.current.isEndingSession).toBe(false);
    expect(result.current.endSessionError).toBeNull();
  });

  it("ends the session and downloads the CSV when handleDownloadCsv is called", async () => {
    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleDownloadCsv();
    });

    await waitFor(() => {
      expect(mockedEndSwipeSession).toHaveBeenCalledWith("session-123");
      expect(mockedDownloadBlob).toHaveBeenCalledWith(
        csvBlob,
        "ukinory_watchlist.csv",
      );
      expect(navigate).toHaveBeenCalledWith("/");
    });

    expect(result.current.isEndingSession).toBe(false);
    expect(result.current.endSessionError).toBeNull();
  });

  it("sets the loading state while ending the session", async () => {
    let resolveEndSession!: (blob: Blob) => void;

    mockedEndSwipeSession.mockReturnValue(
      new Promise<Blob>((resolve) => {
        resolveEndSession = resolve;
      }),
    );

    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleGoHome();
    });

    await waitFor(() => {
      expect(result.current.isEndingSession).toBe(true);
    });

    await act(async () => {
      resolveEndSession(csvBlob);
    });

    await waitFor(() => {
      expect(result.current.isEndingSession).toBe(false);
    });
  });

  it("does not end the session when the ID is undefined", async () => {
    const { result } = renderHook(() =>
      useEndSwipeSession({ id: undefined }),
    );

    act(() => {
      result.current.handleGoHome();
      result.current.handleDownloadCsv();
    });

    await act(async () => {
      await Promise.resolve();
    });

    expect(mockedEndSwipeSession).not.toHaveBeenCalled();
    expect(mockedDownloadBlob).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
    expect(result.current.isEndingSession).toBe(false);
  });

  it("sets the error message when ending the session fails", async () => {
    const error = new Error("Request failed");

    mockedEndSwipeSession.mockRejectedValue(error);
    mockedGetErrorMessage.mockReturnValue("Unable to end session");

    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleGoHome();
    });

    await waitFor(() => {
      expect(result.current.endSessionError).toBe("Unable to end session");
    });

    expect(mockedGetErrorMessage).toHaveBeenCalledWith(error);
    expect(navigate).not.toHaveBeenCalled();
    expect(result.current.isEndingSession).toBe(false);
  });

  it("does not download or navigate when ending the session fails", async () => {
    mockedEndSwipeSession.mockRejectedValue(new Error("Request failed"));

    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleDownloadCsv();
    });

    await waitFor(() => {
      expect(result.current.endSessionError).toBe("Something went wrong");
    });

    expect(mockedDownloadBlob).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("clears the session error when clearEndSessionError is called", async () => {
    mockedEndSwipeSession.mockRejectedValue(new Error("Request failed"));

    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleGoHome();
    });

    await waitFor(() => {
      expect(result.current.endSessionError).toBe("Something went wrong");
    });

    act(() => {
      result.current.clearEndSessionError();
    });

    expect(result.current.endSessionError).toBeNull();
  });

  it("clears a previous error before attempting to end the session again", async () => {
    mockedEndSwipeSession
      .mockRejectedValueOnce(new Error("First failure"))
      .mockResolvedValueOnce(csvBlob);

    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleGoHome();
    });

    await waitFor(() => {
      expect(result.current.endSessionError).toBe("Something went wrong");
    });

    act(() => {
      result.current.handleGoHome();
    });

    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith("/");
      expect(result.current.endSessionError).toBeNull();
    });

    expect(mockedEndSwipeSession).toHaveBeenCalledTimes(2);
  });

  it("prevents a second request while the first request is in progress", async () => {
    let resolveEndSession!: (blob: Blob) => void;

    mockedEndSwipeSession.mockReturnValue(
      new Promise<Blob>((resolve) => {
        resolveEndSession = resolve;
      }),
    );

    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleGoHome();
    });

    await waitFor(() => {
      expect(result.current.isEndingSession).toBe(true);
    });

    act(() => {
      result.current.handleDownloadCsv();
    });

    expect(mockedEndSwipeSession).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveEndSession(csvBlob);
    });

    await waitFor(() => {
      expect(result.current.isEndingSession).toBe(false);
    });
  });

  it("does not download the CSV when only navigating home", async () => {
    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleGoHome();
    });

    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith("/");
    });

    expect(mockedDownloadBlob).not.toHaveBeenCalled();
  });

  it("downloads the CSV before navigating home", async () => {
    const callOrder: string[] = [];

    mockedDownloadBlob.mockImplementation(() => {
      callOrder.push("download");
    });

    navigate.mockImplementation(() => {
      callOrder.push("navigate");
    });

    const { result } = renderHook(() =>
      useEndSwipeSession({ id: "session-123" }),
    );

    act(() => {
      result.current.handleDownloadCsv();
    });

    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith("/");
    });

    expect(callOrder).toEqual(["download", "navigate"]);
  });
});