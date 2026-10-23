
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useBackendWarmup } from "./useBackendWarmup";

vi.mock("../api", () => ({
  apiUrl: vi.fn((path: string) => `http://localhost${path}`),
}));

describe("useBackendWarmup", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-01-01T00:00:00.000Z"));

    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function mockResponse(ok: boolean, status = 200): Response {
    return { ok, status } as Response;
  }

  async function flushPromises() {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  it("starts in checking state and requests the health endpoint", async () => {
    fetchMock.mockResolvedValue(mockResponse(true));

    const { result } = renderHook(() => useBackendWarmup());

    expect(result.current).toBe("checking");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost/health/",
      expect.objectContaining({
        method: "GET",
        cache: "no-store",
        signal: expect.any(AbortSignal),
      }),
    );

    await flushPromises();

    expect(result.current).toBe("ready");
  });

  it("changes to waking after the slow threshold", async () => {
    fetchMock.mockImplementation(() => new Promise<Response>(() => {}));

    const { result } = renderHook(() => useBackendWarmup());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    expect(result.current).toBe("waking");
  });

  it("changes to ready when the health check succeeds", async () => {
    fetchMock.mockResolvedValue(mockResponse(true));

    const { result } = renderHook(() => useBackendWarmup());

    await flushPromises();

    expect(result.current).toBe("ready");
  });

  it("retries after a failed health check", async () => {
    fetchMock
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce(mockResponse(true));

    const { result } = renderHook(() => useBackendWarmup());

    await flushPromises();

    expect(result.current).toBe("waking");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_500);
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current).toBe("ready");
  });

  it("retries when the health endpoint returns a non-success status", async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse(false, 503))
      .mockResolvedValueOnce(mockResponse(true));

    const { result } = renderHook(() => useBackendWarmup());

    await flushPromises();

    expect(result.current).toBe("waking");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_500);
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current).toBe("ready");
  });

  it("aborts a health request after the request timeout", async () => {
    let capturedSignal: AbortSignal | undefined;

    fetchMock.mockImplementation((_input, init) => {
      capturedSignal = init?.signal as AbortSignal;
      return new Promise<Response>(() => {});
    });

    renderHook(() => useBackendWarmup());

    expect(capturedSignal?.aborted).toBe(false);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });

    expect(capturedSignal?.aborted).toBe(true);
  });

  it("marks the backend unreachable after two minutes of failures", async () => {
    fetchMock.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useBackendWarmup());

    await flushPromises();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });

    expect(result.current).toBe("unreachable");
  });

  it("continues retrying every five seconds when unreachable", async () => {
    fetchMock.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useBackendWarmup());

    await flushPromises();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });

    expect(result.current).toBe("unreachable");

    const callsBeforeRetry = fetchMock.mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });

    expect(fetchMock.mock.calls.length).toBeGreaterThan(callsBeforeRetry);
    expect(result.current).toBe("unreachable");
  });

  it("pings again when the browser comes online", async () => {
    fetchMock
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce(mockResponse(true));

    const { result } = renderHook(() => useBackendWarmup());

    await flushPromises();

    expect(result.current).toBe("waking");

    await act(async () => {
      window.dispatchEvent(new Event("online"));
      await Promise.resolve();
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current).toBe("ready");
  });

  it("pings again when the document becomes visible", async () => {
    fetchMock
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce(mockResponse(true));

    const { result } = renderHook(() => useBackendWarmup());

    await flushPromises();

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current).toBe("ready");
  });

  it("does not ping when the document becomes hidden", async () => {
    fetchMock.mockRejectedValue(new Error("Network error"));

    renderHook(() => useBackendWarmup());

    await flushPromises();

    const callsBeforeEvent = fetchMock.mock.calls.length;

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
    });

    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeEvent);
  });

  it("does not update state after the hook is unmounted", async () => {
    let resolveFetch!: (response: Response) => void;

    fetchMock.mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const { result, unmount } = renderHook(() => useBackendWarmup());

    expect(result.current).toBe("checking");

    unmount();

    await act(async () => {
      resolveFetch(mockResponse(true));
      await Promise.resolve();
    });

    expect(result.current).toBe("checking");
  });

  it("cleans up event listeners and pending timers on unmount", async () => {
    fetchMock.mockRejectedValue(new Error("Network error"));

    const removeWindowListener = vi.spyOn(window, "removeEventListener");
    const removeDocumentListener = vi.spyOn(
      document,
      "removeEventListener",
    );

    const { unmount } = renderHook(() => useBackendWarmup());

    await flushPromises();

    unmount();

    expect(removeWindowListener).toHaveBeenCalledWith(
      "online",
      expect.any(Function),
    );
    expect(removeDocumentListener).toHaveBeenCalledWith(
      "visibilitychange",
      expect.any(Function),
    );

    const callsAtUnmount = fetchMock.mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(fetchMock).toHaveBeenCalledTimes(callsAtUnmount);
  });

  it("does not start a duplicate request when a ping is already in flight", async () => {
    let resolveFetch!: (response: Response) => void;

    fetchMock.mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );

    renderHook(() => useBackendWarmup());

    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      window.dispatchEvent(new Event("online"));
      await Promise.resolve();
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFetch(mockResponse(true));
      await Promise.resolve();
    });
  });

  it("clears the slow timer after a successful health check", async () => {
    fetchMock.mockResolvedValue(mockResponse(true));

    const { result } = renderHook(() => useBackendWarmup());

    await flushPromises();

    expect(result.current).toBe("ready");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    expect(result.current).toBe("ready");
  });

  it("keeps the waking state after a later failed retry", async () => {
    fetchMock.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useBackendWarmup());

    await flushPromises();

    expect(result.current).toBe("waking");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_500);
    });

    expect(result.current).toBe("waking");
  });

  it("does not retry when a failed request completes after unmount", async () => {
    let rejectFetch!: (error: Error) => void;

    fetchMock.mockImplementation(
      () =>
        new Promise<Response>((_resolve, reject) => {
          rejectFetch = reject;
        }),
    );

    const { unmount } = renderHook(() => useBackendWarmup());

    expect(fetchMock).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      rejectFetch(new Error("Network error after unmount"));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});