import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Dispatch, SetStateAction } from "react";

import {
  buildRoomSocketUrl,
  generateComparison,
  getComparisonResult,
  getRoom,
  type ComparisonResult,
  type RoomState,
} from "../services/comparisons";
import type { FatalSessionError } from "../services/sessions";
import { deriveLobbyPhase, useLiveSession } from "./useLiveSession";
import { useComparisonRoom } from "./useComparisonRoom";

vi.mock("../services/comparisons", () => ({
  buildRoomSocketUrl: vi.fn(),
  generateComparison: vi.fn(),
  getComparisonResult: vi.fn(),
  getRoom: vi.fn(),
}));

vi.mock("./useLiveSession", () => ({
  deriveLobbyPhase: vi.fn(),
  useLiveSession: vi.fn(),
}));

const mockedUseLiveSession = vi.mocked(useLiveSession);
const mockedDeriveLobbyPhase = vi.mocked(deriveLobbyPhase);
const mockedGenerateComparison = vi.mocked(generateComparison);
const mockedGetComparisonResult = vi.mocked(getComparisonResult);

type LiveSessionResult = {
  state: RoomState | null;
  setState: Dispatch<SetStateAction<RoomState | null>>;
  error: string | null;
  setError: Dispatch<SetStateAction<string | null>>;
  fatal: FatalSessionError | null;
  socketConnected: boolean;
  refresh: () => Promise<void>;
  reload: () => void;
  handleFailure: (err: unknown, silent?: boolean) => void;
};

function makeRoom(overrides: Partial<RoomState> = {}): RoomState {
  return {
    status: "WAITING",
    partner_joined: false,
    you_have_data: false,
    partner_has_data: false,
    generation_status: null,
    ...overrides,
  } as RoomState;
}

function makeResult(): ComparisonResult {
  return {} as ComparisonResult;
}

function makeLiveSession(
  overrides: Partial<LiveSessionResult> = {},
): LiveSessionResult {
  return {
    state: null,
    setState: vi.fn(),
    setError: vi.fn(),
    error: null,
    fatal: null,
    socketConnected: false,
    refresh: vi.fn().mockResolvedValue(undefined),
    reload: vi.fn(),
    handleFailure: vi.fn(),
    ...overrides,
  };
}

function configureLiveSession(
  overrides: Partial<LiveSessionResult> = {},
) {
  const value = makeLiveSession(overrides);

  (
    mockedUseLiveSession as unknown as {
      mockReturnValue: (value: LiveSessionResult) => void;
    }
  ).mockReturnValue(value);

  return value;
}

function makeReadyRoom(
  overrides: Partial<RoomState> = {},
): RoomState {
  return makeRoom({
    status: "WAITING",
    partner_joined: true,
    you_have_data: true,
    partner_has_data: true,
    generation_status: "pending",
    ...overrides,
  });
}

describe("useComparisonRoom", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockedDeriveLobbyPhase.mockReturnValue(null);
    mockedGenerateComparison.mockResolvedValue(makeRoom());
    mockedGetComparisonResult.mockResolvedValue(makeResult());

    configureLiveSession();
  });

  it("returns the initial room and comparison state", () => {
    const room = makeRoom();
    configureLiveSession({ state: room });

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    expect(result.current.room).toBe(room);
    expect(result.current.result).toBeNull();
    expect(result.current.phase).toBe("generating");
    expect(result.current.isGenerating).toBe(false);
    expect(result.current.roomClosed).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.fatal).toBeNull();
  });

  it("configures the live session with the room API functions", () => {
    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedUseLiveSession).toHaveBeenCalledWith(
      expect.objectContaining({
        sessionId: "room-123",
        fetchState: getRoom,
        socketUrl: buildRoomSocketUrl,
        onState: expect.any(Function),
      }),
    );
  });

  it("keeps the live session enabled before the result is loaded", () => {
    renderHook(() => useComparisonRoom("room-123"));

    const options = mockedUseLiveSession.mock.calls[0][0] as {
      enabled?: boolean;
    };

    expect(options.enabled).not.toBe(false);
  });

  it("keeps the live session enabled once a comparison result is loaded", async () => {
    const room = makeRoom({ generation_status: "ready" });
    configureLiveSession({ state: room });

    const comparisonResult = makeResult();
    mockedGetComparisonResult.mockResolvedValue(comparisonResult);

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(result.current.result).toBe(comparisonResult);
    });

    const lastOptions = mockedUseLiveSession.mock.lastCall?.[0] as {
      enabled?: boolean;
    };

    // Needed so the user notices when their partner leaves the room.
    expect(lastOptions.enabled).not.toBe(false);
  });

  it("uses the lobby phase returned by deriveLobbyPhase", () => {
    const room = makeRoom();
    configureLiveSession({ state: room });

    const lobbyPhase = "lobby" as ReturnType<typeof deriveLobbyPhase>;
    mockedDeriveLobbyPhase.mockReturnValue(lobbyPhase);

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    expect(result.current.phase).toBe(lobbyPhase);
    expect(mockedDeriveLobbyPhase).toHaveBeenCalledWith(room);
  });

  it("loads the comparison result when generation is ready", async () => {
    const room = makeRoom({ generation_status: "ready" });
    configureLiveSession({ state: room });

    const comparisonResult = makeResult();
    mockedGetComparisonResult.mockResolvedValue(comparisonResult);

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(result.current.result).toBe(comparisonResult);
    });

    expect(mockedGetComparisonResult).toHaveBeenCalledWith("room-123");
    expect(result.current.phase).toBe("ready");
  });

  it("passes result-fetch failures to handleFailure", async () => {
    const room = makeRoom({ generation_status: "ready" });
    const handleFailure = vi.fn();
    configureLiveSession({ state: room, handleFailure });

    const error = new Error("Could not load comparison");
    mockedGetComparisonResult.mockRejectedValue(error);

    renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(handleFailure).toHaveBeenCalledWith(error);
    });
  });

  it("does not load a comparison result unless generation is ready", () => {
    configureLiveSession({
      state: makeRoom({ generation_status: "pending" }),
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGetComparisonResult).not.toHaveBeenCalled();
  });

  it("returns failed phase when generation has failed", () => {
    configureLiveSession({
      state: makeRoom({ generation_status: "failed" }),
    });

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    expect(result.current.phase).toBe("failed");
  });

  it("starts generation when both participants have data", async () => {
    configureLiveSession({ state: makeReadyRoom() });

    renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledWith("room-123");
    });
  });

  it("does not start generation when the partner has not joined", () => {
    configureLiveSession({
      state: makeReadyRoom({ partner_joined: false }),
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("does not start generation when the current participant has no data", () => {
    configureLiveSession({
      state: makeReadyRoom({ you_have_data: false }),
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("does not start generation when the partner has no data", () => {
    configureLiveSession({
      state: makeReadyRoom({ partner_has_data: false }),
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("does not start generation for a finished room", () => {
    configureLiveSession({
      state: makeReadyRoom({ status: "FINISHED" }),
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("does not start generation when generation is already ready", () => {
    configureLiveSession({
      state: makeReadyRoom({ generation_status: "ready" }),
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("does not start generation when generation has failed", () => {
    configureLiveSession({
      state: makeReadyRoom({ generation_status: "failed" }),
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("sets the generated room and clears the error after successful generation", async () => {
    const setRoom = vi.fn();
    const setError = vi.fn();
    const generatedRoom = makeRoom({ generation_status: "ready" });

    configureLiveSession({
      state: makeReadyRoom(),
      setState: setRoom,
      setError,
    });

    mockedGenerateComparison.mockResolvedValue(generatedRoom);

    renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(setRoom).toHaveBeenCalledWith(generatedRoom);
    });

    expect(setError).toHaveBeenCalledWith(null);
  });

  it("passes generation failures to handleFailure", async () => {
    const error = new Error("Generation failed");
    const handleFailure = vi.fn();

    configureLiveSession({
      state: makeReadyRoom(),
      handleFailure,
    });

    mockedGenerateComparison.mockRejectedValue(error);

    renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(handleFailure).toHaveBeenCalledWith(error);
    });
  });

  it("does not fetch or generate without a room ID", () => {
    configureLiveSession({
      state: makeReadyRoom({ generation_status: "ready" }),
    });

    renderHook(() => useComparisonRoom(undefined));

    expect(mockedGetComparisonResult).not.toHaveBeenCalled();
    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("does not update the result if the result request is cancelled", async () => {
    let resolveResult!: (value: ComparisonResult) => void;

    mockedGetComparisonResult.mockImplementation(
      () =>
        new Promise<ComparisonResult>((resolve) => {
          resolveResult = resolve;
        }),
    );

    configureLiveSession({
      state: makeRoom({ generation_status: "ready" }),
    });

    const { result, unmount } = renderHook(() =>
      useComparisonRoom("room-123"),
    );

    await waitFor(() => {
      expect(mockedGetComparisonResult).toHaveBeenCalledWith("room-123");
    });

    unmount();

    await act(async () => {
      resolveResult(makeResult());
      await Promise.resolve();
    });

    expect(result.current.result).toBeNull();
  });

  it("retries generation when retryGeneration is called", async () => {
    configureLiveSession({ state: makeReadyRoom() });

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      result.current.retryGeneration();
    });

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(2);
    });
  });

  it("clears the error when retrying generation", () => {
    const setError = vi.fn();

    configureLiveSession({
      state: makeRoom(),
      setError,
    });

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    act(() => {
      result.current.retryGeneration();
    });

    expect(setError).toHaveBeenCalledWith(null);
  });

  it("exposes refresh, reload, error, and fatal state from the live session", () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    const reload = vi.fn();
    const error = "Room error";
    const fatal: FatalSessionError = "closed";

    configureLiveSession({
      error,
      fatal,
      refresh,
      reload,
    });

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    expect(result.current.refresh).toBe(refresh);
    expect(result.current.reload).toBe(reload);
    expect(result.current.error).toBe(error);
    expect(result.current.fatal).toBe(fatal);
  });

  it("does not start generation when the session has a fatal error", () => {
    configureLiveSession({
      state: makeReadyRoom(),
      fatal: "closed",
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("does not fetch the comparison result when the session has a fatal error", () => {
    configureLiveSession({
      state: makeRoom({ generation_status: "ready" }),
      fatal: "closed",
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGetComparisonResult).not.toHaveBeenCalled();
  });

  it("closes a finished room whose comparison is not ready", () => {
    renderHook(() => useComparisonRoom("room-123"));

    const options = mockedUseLiveSession.mock.calls[0][0] as {
      onState?: (room: RoomState) => FatalSessionError | undefined;
    };

    for (const generation_status of [
      null,
      "pending",
      "running",
      "needs_data",
      "failed",
    ] as RoomState["generation_status"][]) {
      expect(
        options.onState?.(makeRoom({ status: "FINISHED", generation_status })),
      ).toBe("closed");
    }
  });

  it("closes a finished room whatever the comparison status", () => {
    renderHook(() => useComparisonRoom("room-123"));

    const options = mockedUseLiveSession.mock.calls[0][0] as {
      onState?: (room: RoomState) => FatalSessionError | undefined;
    };

    for (const generation_status of [
      null,
      "pending",
      "running",
      "ready",
      "needs_data",
      "failed",
    ] as RoomState["generation_status"][]) {
      expect(
        options.onState?.(makeRoom({ status: "FINISHED", generation_status })),
      ).toBe("closed");
    }
  });

  it("does not close rooms that are still waiting or active", () => {
    renderHook(() => useComparisonRoom("room-123"));

    const options = mockedUseLiveSession.mock.calls[0][0] as {
      onState?: (room: RoomState) => FatalSessionError | undefined;
    };

    expect(options.onState?.(makeRoom({ status: "WAITING" }))).toBeUndefined();
    expect(options.onState?.(makeRoom({ status: "ACTIVE" }))).toBeUndefined();
  });

  describe("roomClosed", () => {
    it("is false while there is no room yet", () => {
      configureLiveSession({ state: null });

      const { result } = renderHook(() => useComparisonRoom("room-123"));

      expect(result.current.roomClosed).toBe(false);
    });

    it.each(["WAITING", "ACTIVE"])("is false for a %s room", (status) => {
      configureLiveSession({
        state: makeRoom({ status: status as RoomState["status"] }),
      });

      const { result } = renderHook(() => useComparisonRoom("room-123"));

      expect(result.current.roomClosed).toBe(false);
    });

    it("is true for a finished room", () => {
      configureLiveSession({
        state: makeRoom({ status: "FINISHED" }),
      });

      const { result } = renderHook(() => useComparisonRoom("room-123"));

      expect(result.current.roomClosed).toBe(true);
    });

    it("is true when the partner left after the result was generated", async () => {
      const comparisonResult = makeResult();
      mockedGetComparisonResult.mockResolvedValue(comparisonResult);

      configureLiveSession({
        state: makeRoom({ status: "FINISHED", generation_status: "ready" }),
      });

      const { result } = renderHook(() => useComparisonRoom("room-123"));

      await waitFor(() => {
        expect(result.current.result).toBe(comparisonResult);
      });

      expect(result.current.phase).toBe("ready");
      expect(result.current.roomClosed).toBe(true);
    });

    it("turns true when a room that had the result is finished by the partner", async () => {
      const comparisonResult = makeResult();
      mockedGetComparisonResult.mockResolvedValue(comparisonResult);

      const live = configureLiveSession({
        state: makeRoom({ status: "ACTIVE", generation_status: "ready" }),
      });

      const { result, rerender } = renderHook(() =>
        useComparisonRoom("room-123"),
      );

      await waitFor(() => {
        expect(result.current.result).toBe(comparisonResult);
      });

      expect(result.current.roomClosed).toBe(false);

      live.state = makeRoom({ status: "FINISHED", generation_status: "ready" });
      rerender();

      expect(result.current.roomClosed).toBe(true);
      expect(result.current.phase).toBe("ready");
    });
  });

  it("still loads the result of a finished room whose comparison is ready", async () => {
    const comparisonResult = makeResult();
    mockedGetComparisonResult.mockResolvedValue(comparisonResult);

    configureLiveSession({
      state: makeRoom({ status: "FINISHED", generation_status: "ready" }),
    });

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(result.current.result).toBe(comparisonResult);
    });

    expect(mockedGetComparisonResult).toHaveBeenCalledWith("room-123");
    expect(result.current.phase).toBe("ready");
  });

  it.each([null, "pending", "needs_data"] as RoomState["generation_status"][])(
    "starts generation when the generation status is %s",
    async (generation_status) => {
      configureLiveSession({ state: makeReadyRoom({ generation_status }) });

      renderHook(() => useComparisonRoom("room-123"));

      await waitFor(() => {
        expect(mockedGenerateComparison).toHaveBeenCalledWith("room-123");
      });
    },
  );

  it("does not start generation while it is already running", () => {
    configureLiveSession({
      state: makeReadyRoom({
        generation_status: "running" as RoomState["generation_status"],
      }),
    });

    renderHook(() => useComparisonRoom("room-123"));

    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("starts generation for a room that is already active", async () => {
    configureLiveSession({ state: makeReadyRoom({ status: "ACTIVE" }) });

    renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledWith("room-123");
    });
  });

  it("starts generation again when the generation key changes", async () => {
    const live = configureLiveSession({
      state: makeReadyRoom({ generation_status: "needs_data" }),
    });

    const { result, rerender } = renderHook(() =>
      useComparisonRoom("room-123"),
    );

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(result.current.isGenerating).toBe(false);
    });

    live.state = makeReadyRoom({ generation_status: "pending" });
    rerender();

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(2);
    });
  });

  it("starts generation again once the room becomes ready again after losing readiness", async () => {
    const live = configureLiveSession({ state: makeReadyRoom() });

    const { result, rerender } = renderHook(() =>
      useComparisonRoom("room-123"),
    );

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(result.current.isGenerating).toBe(false);
    });

    live.state = makeReadyRoom({ partner_has_data: false });
    rerender();

    expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);

    live.state = makeReadyRoom();
    rerender();

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(2);
    });
  });

  it("starts generation again when the partner leaves and rejoins with the same data", async () => {
    const live = configureLiveSession({ state: makeReadyRoom() });

    const { result, rerender } = renderHook(() =>
      useComparisonRoom("room-123"),
    );

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(result.current.isGenerating).toBe(false);
    });

    live.state = makeReadyRoom({
      partner_joined: false,
      partner_has_data: null,
    });
    rerender();

    expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);

    live.state = makeReadyRoom();
    rerender();

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(2);
    });
  });

  it("reports isGenerating while a generation request is in flight", async () => {
    let resolveGeneration!: (room: RoomState) => void;

    mockedGenerateComparison.mockImplementation(
      () =>
        new Promise<RoomState>((resolve) => {
          resolveGeneration = resolve;
        }),
    );

    configureLiveSession({ state: makeReadyRoom() });

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(result.current.isGenerating).toBe(true);
    });

    await act(async () => {
      resolveGeneration(makeRoom({ generation_status: "ready" }));
      await Promise.resolve();
    });

    expect(result.current.isGenerating).toBe(false);
  });

  it("stops reporting isGenerating after a generation failure", async () => {
    const handleFailure = vi.fn();
    mockedGenerateComparison.mockRejectedValue(new Error("Generation failed"));

    configureLiveSession({ state: makeReadyRoom(), handleFailure });

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(handleFailure).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(result.current.isGenerating).toBe(false);
    });
  });

  it("does not generate when retry is called without a room ID", async () => {
    const { result } = renderHook(() => useComparisonRoom(undefined));

    await act(async () => {
      result.current.retryGeneration();
      await Promise.resolve();
    });

    expect(mockedGenerateComparison).not.toHaveBeenCalled();
  });

  it("does not start another generation while one is already in progress", async () => {
    let resolveGeneration!: (room: RoomState) => void;

    mockedGenerateComparison.mockImplementation(
      () =>
        new Promise<RoomState>((resolve) => {
          resolveGeneration = resolve;
        }),
    );

    configureLiveSession({ state: makeReadyRoom() });

    const { result } = renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);
    });

    act(() => {
      result.current.retryGeneration();
    });

    expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveGeneration(makeRoom({ generation_status: "ready" }));
      await Promise.resolve();
    });
  });

  it("does not start generation again when the generation key has not changed", async () => {
    const room = makeReadyRoom();
    const setState = vi.fn();

    configureLiveSession({
      state: room,
      setState,
    });

    const { rerender } = renderHook(() =>
      useComparisonRoom("room-123"),
    );

    await waitFor(() => {
      expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);
    });

    configureLiveSession({
      state: { ...room },
      setState,
    });

    rerender();

    expect(mockedGenerateComparison).toHaveBeenCalledTimes(1);
  });

  it("ignores result-fetch failures when the request has been cancelled", async () => {
    let rejectResult!: (error: Error) => void;
    const handleFailure = vi.fn();

    mockedGetComparisonResult.mockImplementation(
      () =>
        new Promise<ComparisonResult>((_resolve, reject) => {
          rejectResult = reject;
        }),
    );

    configureLiveSession({
      state: makeRoom({ generation_status: "ready" }),
      handleFailure,
    });

    const { unmount } = renderHook(() => useComparisonRoom("room-123"));

    await waitFor(() => {
      expect(mockedGetComparisonResult).toHaveBeenCalledWith("room-123");
    });

    unmount();

    await act(async () => {
      rejectResult(new Error("Request failed after unmount"));
      await Promise.resolve();
    });

    expect(handleFailure).not.toHaveBeenCalled();
  });
});