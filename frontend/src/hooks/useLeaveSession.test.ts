import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useNavigate } from "react-router-dom";

import { useLeaveSession } from "./useLeaveSession";

vi.mock("react-router-dom", () => ({
  useNavigate: vi.fn(),
}));

const mockedUseNavigate = vi.mocked(useNavigate);

describe("useLeaveSession", () => {
  const navigate = vi.fn();
  const leave = vi.fn<(
    sessionId: string,
  ) => Promise<unknown>>();

  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseNavigate.mockReturnValue(navigate);
    leave.mockResolvedValue(undefined);
  });

  it("returns the initial state and handlers", () => {
    const { result } = renderHook(() =>
      useLeaveSession("session-123", leave, "session"),
    );

    expect(result.current.isLeaving).toBe(false);
    expect(result.current.leaveError).toBeNull();
    expect(result.current.handleLeave).toEqual(expect.any(Function));
    expect(result.current.clearLeaveError).toEqual(expect.any(Function));
  });

  it("calls leave with the session ID and navigates home on success", async () => {
    const { result } = renderHook(() =>
      useLeaveSession("session-123", leave, "session"),
    );

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(leave).toHaveBeenCalledTimes(1);
    expect(leave).toHaveBeenCalledWith("session-123");
    expect(navigate).toHaveBeenCalledWith("/");
    expect(result.current.isLeaving).toBe(false);
    expect(result.current.leaveError).toBeNull();
  });

  it("sets isLeaving while the leave request is pending", async () => {
    let resolveLeave!: (value: unknown) => void;

    leave.mockReturnValue(
      new Promise<unknown>((resolve) => {
        resolveLeave = resolve;
      }),
    );

    const { result } = renderHook(() =>
      useLeaveSession("session-123", leave, "session"),
    );

    act(() => {
      void result.current.handleLeave();
    });

    await waitFor(() => {
      expect(result.current.isLeaving).toBe(true);
    });

    await act(async () => {
      resolveLeave(undefined);
    });

    await waitFor(() => {
      expect(result.current.isLeaving).toBe(false);
    });
  });

  it("does nothing when the session ID is undefined", async () => {
    const { result } = renderHook(() =>
      useLeaveSession(undefined, leave, "session"),
    );

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(leave).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
    expect(result.current.isLeaving).toBe(false);
    expect(result.current.leaveError).toBeNull();
  });

  it("sets an error when leaving fails for a session", async () => {
    leave.mockRejectedValue(new Error("Network failure"));

    const { result } = renderHook(() =>
      useLeaveSession("session-123", leave, "session"),
    );

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(result.current.leaveError).toBe(
      "Unable to leave the session. Please try again.",
    );
    expect(result.current.isLeaving).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("sets an error when leaving fails for a room", async () => {
    leave.mockRejectedValue(new Error("Network failure"));

    const { result } = renderHook(() =>
      useLeaveSession("room-123", leave, "room"),
    );

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(result.current.leaveError).toBe(
      "Unable to leave the room. Please try again.",
    );
    expect(result.current.isLeaving).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("clears the leave error when clearLeaveError is called", async () => {
    leave.mockRejectedValueOnce(new Error("Network failure"));

    const { result } = renderHook(() =>
      useLeaveSession("session-123", leave, "session"),
    );

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(result.current.leaveError).not.toBeNull();

    act(() => {
      result.current.clearLeaveError();
    });

    expect(result.current.leaveError).toBeNull();
  });

  it("clears a previous error before attempting to leave again", async () => {
    leave
      .mockRejectedValueOnce(new Error("First failure"))
      .mockResolvedValueOnce(undefined);

    const { result } = renderHook(() =>
      useLeaveSession("session-123", leave, "session"),
    );

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(result.current.leaveError).toBe(
      "Unable to leave the session. Please try again.",
    );

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(leave).toHaveBeenCalledTimes(2);
    expect(result.current.leaveError).toBeNull();
    expect(navigate).toHaveBeenCalledWith("/");
  });

  it("does not start a second leave request while the first is pending", async () => {
    let resolveLeave!: (value: unknown) => void;

    leave.mockReturnValue(
      new Promise<unknown>((resolve) => {
        resolveLeave = resolve;
      }),
    );

    const { result } = renderHook(() =>
      useLeaveSession("session-123", leave, "session"),
    );

    let firstRequest!: Promise<void>;

    act(() => {
      firstRequest = result.current.handleLeave();
    });

    await waitFor(() => {
      expect(result.current.isLeaving).toBe(true);
    });

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(leave).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveLeave(undefined);
      await firstRequest;
    });

    expect(result.current.isLeaving).toBe(false);
    expect(navigate).toHaveBeenCalledTimes(1);
  });

  it("uses the updated session ID after rerendering", async () => {
    const { result, rerender } = renderHook(
      ({ sessionId }: { sessionId: string | undefined }) =>
        useLeaveSession(sessionId, leave, "session"),
      {
        initialProps: { sessionId: "session-123" },
      },
    );

    rerender({ sessionId: "session-456" });

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(leave).toHaveBeenCalledWith("session-456");
  });

  it("uses the updated leave function after rerendering", async () => {
    const replacementLeave = vi.fn().mockResolvedValue(undefined);

    const { result, rerender } = renderHook(
      ({ leaveFn }: { leaveFn: typeof leave }) =>
        useLeaveSession("session-123", leaveFn, "session"),
      {
        initialProps: { leaveFn: leave },
      },
    );

    rerender({ leaveFn: replacementLeave });

    await act(async () => {
      await result.current.handleLeave();
    });

    expect(leave).not.toHaveBeenCalled();
    expect(replacementLeave).toHaveBeenCalledWith("session-123");
  });
});