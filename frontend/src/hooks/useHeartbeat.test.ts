import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { sendHeartbeat } from "../services/swipeSessions";
import {
  HEARTBEAT_INTERVAL_MS,
  useHeartbeat,
} from "./useHeartbeat";

vi.mock("../services/swipeSessions", () => ({
  sendHeartbeat: vi.fn(),
}));

const mockedSendHeartbeat = vi.mocked(sendHeartbeat);

describe("useHeartbeat", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("does not send a heartbeat when the session ID is undefined", () => {
    renderHook(() => useHeartbeat(undefined, true, { immediate: true }));

    expect(mockedSendHeartbeat).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not send a heartbeat when disabled", () => {
    renderHook(() =>
      useHeartbeat("session-123", false, { immediate: true }),
    );

    expect(mockedSendHeartbeat).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("sends an immediate heartbeat when immediate is enabled", () => {
    renderHook(() => useHeartbeat("session-123", true, { immediate: true }));

    expect(mockedSendHeartbeat).toHaveBeenCalledTimes(1);
    expect(mockedSendHeartbeat).toHaveBeenCalledWith("session-123");
  });

  it("does not send an immediate heartbeat by default", () => {
    renderHook(() => useHeartbeat("session-123", true));

    expect(mockedSendHeartbeat).not.toHaveBeenCalled();
  });

  it("schedules a heartbeat at the configured interval", () => {
    renderHook(() => useHeartbeat("session-123", true));

    expect(vi.getTimerCount()).toBe(1);

    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS - 1);

    expect(mockedSendHeartbeat).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);

    expect(mockedSendHeartbeat).toHaveBeenCalledTimes(1);
    expect(mockedSendHeartbeat).toHaveBeenCalledWith("session-123");
  });

  it("sends repeated heartbeats at each interval", () => {
    renderHook(() => useHeartbeat("session-123", true));

    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS * 3);

    expect(mockedSendHeartbeat).toHaveBeenCalledTimes(3);
    expect(mockedSendHeartbeat).toHaveBeenNthCalledWith(1, "session-123");
    expect(mockedSendHeartbeat).toHaveBeenNthCalledWith(2, "session-123");
    expect(mockedSendHeartbeat).toHaveBeenNthCalledWith(3, "session-123");
  });

  it("sends an immediate heartbeat and continues on the interval", () => {
    renderHook(() => useHeartbeat("session-123", true, { immediate: true }));

    expect(mockedSendHeartbeat).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS * 2);

    expect(mockedSendHeartbeat).toHaveBeenCalledTimes(3);
  });

  it("clears the interval when the hook unmounts", () => {
    const { unmount } = renderHook(() => useHeartbeat("session-123", true));

    expect(vi.getTimerCount()).toBe(1);

    unmount();

    expect(vi.getTimerCount()).toBe(0);

    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS * 2);

    expect(mockedSendHeartbeat).not.toHaveBeenCalled();
  });

  it("clears the old interval when the session ID changes", () => {
    const { rerender } = renderHook(
      ({ sessionId }: { sessionId: string | undefined }) =>
        useHeartbeat(sessionId, true),
      {
        initialProps: { sessionId: "session-123" },
      },
    );

    expect(vi.getTimerCount()).toBe(1);

    rerender({ sessionId: "session-456" });

    expect(vi.getTimerCount()).toBe(1);

    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS);

    expect(mockedSendHeartbeat).toHaveBeenCalledTimes(1);
    expect(mockedSendHeartbeat).toHaveBeenCalledWith("session-456");
  });

  it("clears the interval when heartbeat is disabled", () => {
    const { rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useHeartbeat("session-123", enabled),
      {
        initialProps: { enabled: true },
      },
    );

    expect(vi.getTimerCount()).toBe(1);

    rerender({ enabled: false });

    expect(vi.getTimerCount()).toBe(0);

    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS * 2);

    expect(mockedSendHeartbeat).not.toHaveBeenCalled();
  });

  it("starts the interval again when heartbeat is re-enabled", () => {
    const { rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useHeartbeat("session-123", enabled),
      {
        initialProps: { enabled: false },
      },
    );

    expect(vi.getTimerCount()).toBe(0);

    rerender({ enabled: true });

    expect(vi.getTimerCount()).toBe(1);

    vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS);

    expect(mockedSendHeartbeat).toHaveBeenCalledTimes(1);
    expect(mockedSendHeartbeat).toHaveBeenCalledWith("session-123");
  });

  it("restarts the interval when the immediate option changes", () => {
    const { rerender } = renderHook(
      ({ immediate }: { immediate: boolean }) =>
        useHeartbeat("session-123", true, { immediate }),
      {
        initialProps: { immediate: false },
      },
    );

    expect(mockedSendHeartbeat).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(1);

    rerender({ immediate: true });

    expect(mockedSendHeartbeat).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(1);
  });
});