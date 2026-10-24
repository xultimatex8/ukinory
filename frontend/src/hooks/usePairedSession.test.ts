import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildSessionSocketUrl,
  getPairedSessionState,
  getSessionMatches,
  startSwipeSession,
  type PairedSessionState,
} from "../services/swipeSessions";
import { classifyFatalError } from "../services/sessions";
import { getErrorMessage } from "../utils/errors";
import { useHeartbeat } from "./useHeartbeat";
import { useLiveSession } from "./useLiveSession";
import { usePairedSession } from "./usePairedSession";

vi.mock("../services/swipeSessions", () => ({
  buildSessionSocketUrl: vi.fn(),
  getPairedSessionState: vi.fn(),
  getSessionMatches: vi.fn(),
  startSwipeSession: vi.fn(),
}));

vi.mock("../services/sessions", () => ({
  classifyFatalError: vi.fn(),
}));

vi.mock("../utils/errors", () => ({
  getErrorMessage: vi.fn(),
}));

vi.mock("./useHeartbeat", () => ({
  useHeartbeat: vi.fn(),
}));

vi.mock("./useLiveSession", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./useLiveSession")>();

  return {
    ...actual,
    deriveLobbyPhase: vi.fn((state: PairedSessionState) => {
      if (!state.partner_joined) return "waiting_partner";
      if (!state.you_have_data) return "needs_import";
      if (state.partner_has_data === false) return "waiting_partner_data";
      return null;
    }),
    useLiveSession: vi.fn(),
  };
});

const mockedBuildSessionSocketUrl = vi.mocked(buildSessionSocketUrl);
const mockedGetPairedSessionState = vi.mocked(getPairedSessionState);
const mockedGetSessionMatches = vi.mocked(getSessionMatches);
const mockedStartSwipeSession = vi.mocked(startSwipeSession);
const mockedClassifyFatalError = vi.mocked(classifyFatalError);
const mockedGetErrorMessage = vi.mocked(getErrorMessage);
const mockedUseHeartbeat = vi.mocked(useHeartbeat);
const mockedUseLiveSession = vi.mocked(useLiveSession);

function makePairedState(
  overrides: Partial<PairedSessionState> = {},
): PairedSessionState {
  return {
    status: "WAITING",
    partner_joined: true,
    you_have_data: true,
    partner_has_data: true,
    current_user_id: "user-1",
    matches_count: 0,
    ...overrides,
  } as PairedSessionState;
}

function makeMatchRecord(
  candidateId: string,
  title: string,
  releaseYear: number | null,
) {
  return {
    candidate_id: candidateId,
    matched_at: null,
    movie: {
      tmdb_id: 0,
      title,
      release_year: releaseYear,
      poster_url: "",
    },
  };
}

function makeLiveSessionResult(overrides: Record<string, unknown> = {}) {
  return {
    state: null as PairedSessionState | null,
    error: null as string | null,
    fatal: null,
    socketConnected: false,
    refresh: vi.fn().mockResolvedValue(undefined),
    reload: vi.fn(),
    handleFailure: vi.fn(),
    ...overrides,
  };
}

type LiveOptions = {
  enabled: boolean;
  onState: (state: PairedSessionState) => unknown;
  onMessage: (
    event: Record<string, unknown>,
    refresh: () => Promise<void>,
  ) => void;
};

const lastLiveOptions = () =>
  mockedUseLiveSession.mock.calls.at(-1)?.[0] as unknown as LiveOptions;

const flushAsync = async () => {
  await vi.advanceTimersByTimeAsync(0);
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
};

describe("usePairedSession", () => {
  let liveSession: ReturnType<typeof makeLiveSessionResult>;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    mockedBuildSessionSocketUrl.mockReturnValue("ws://localhost/session");
    mockedGetPairedSessionState.mockResolvedValue(makePairedState());
    mockedGetSessionMatches.mockResolvedValue([]);
    mockedStartSwipeSession.mockResolvedValue(
      {} as Awaited<ReturnType<typeof startSwipeSession>>,
    );
    mockedClassifyFatalError.mockReturnValue(null);
    mockedGetErrorMessage.mockReturnValue("Unable to start session");

    liveSession = makeLiveSessionResult();

    mockedUseLiveSession.mockReturnValue(
      liveSession as unknown as ReturnType<typeof useLiveSession>,
    );
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("returns the initial session state and derived phase", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    expect(result.current.state).toBeNull();
    expect(result.current.phase).toBe("loading");
    expect(result.current.error).toBeNull();
    expect(result.current.fatal).toBeNull();
    expect(result.current.startError).toBeNull();
    expect(result.current.socketConnected).toBe(false);
    expect(result.current.hasBeenActive).toBe(false);
    expect(result.current.ended).toBe(false);
    expect(result.current.matchCount).toBe(0);
    expect(result.current.toast).toBeNull();
    expect(result.current.activity).toBeNull();
  });

  it("configures the live session with the expected callbacks", () => {
    renderHook(() => usePairedSession("session-1"));

    expect(mockedUseLiveSession).toHaveBeenCalledWith(
      expect.objectContaining({
        sessionId: "session-1",
        fetchState: getPairedSessionState,
        socketUrl: buildSessionSocketUrl,
        enabled: true,
        onState: expect.any(Function),
        onMessage: expect.any(Function),
      }),
    );
  });

  it("disables live session polling once an ended event arrives", () => {
    renderHook(() => usePairedSession("session-1"));

    expect(lastLiveOptions().enabled).toBe(true);

    act(() => {
      lastLiveOptions().onMessage(
        { event: "session.updated", reason: "ended" },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(mockedUseLiveSession).toHaveBeenLastCalledWith(
      expect.objectContaining({ sessionId: "session-1", enabled: false }),
    );
  });

  it("disables live session polling once the state reports a finished session", () => {
    renderHook(() => usePairedSession("session-1"));

    act(() => {
      lastLiveOptions().onState(makePairedState({ status: "FINISHED" }));
    });

    expect(lastLiveOptions().enabled).toBe(false);
  });

  it("keeps live session polling enabled for other session updates", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));
    const refresh = vi.fn().mockResolvedValue(undefined);

    act(() => {
      lastLiveOptions().onMessage(
        { event: "session.updated", reason: "partner_left" },
        refresh,
      );
    });

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(result.current.ended).toBe(false);
    expect(lastLiveOptions().enabled).toBe(true);
  });

  it("bootstraps session matches after the initial timer", async () => {
    renderHook(() => usePairedSession("session-1"));

    expect(mockedGetSessionMatches).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedGetSessionMatches).toHaveBeenCalledWith("session-1");
  });

  it("does not bootstrap matches when the session ID is missing", async () => {
    renderHook(() => usePairedSession(undefined));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedGetSessionMatches).not.toHaveBeenCalled();
  });

  it("does not throw when bootstrapping matches fails", async () => {
    mockedGetSessionMatches.mockRejectedValueOnce(new Error("Network error"));

    renderHook(() => usePairedSession("session-1"));

    await expect(
      act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      }),
    ).resolves.not.toThrow();
  });

  it("uses the loading phase when no session state is available", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    expect(result.current.phase).toBe("loading");
  });

  it("uses the active phase for an active session", () => {
    liveSession.state = makePairedState({ status: "ACTIVE" });

    const { result } = renderHook(() => usePairedSession("session-1"));

    expect(result.current.phase).toBe("active");
  });

  it("uses the closed phase for a finished session", () => {
    liveSession.state = makePairedState({ status: "FINISHED" });

    const { result } = renderHook(() => usePairedSession("session-1"));

    expect(result.current.phase).toBe("closed");
  });

  it("uses the waiting partner phase when the partner has not joined", () => {
    liveSession.state = makePairedState({ partner_joined: false });

    const { result } = renderHook(() => usePairedSession("session-1"));

    expect(result.current.phase).toBe("waiting_partner");
  });

  it("uses the needs import phase when the current user has no data", () => {
    liveSession.state = makePairedState({ you_have_data: false });

    const { result } = renderHook(() => usePairedSession("session-1"));

    expect(result.current.phase).toBe("needs_import");
  });

  it("uses the waiting partner data phase when the partner has no data", () => {
    liveSession.state = makePairedState({ partner_has_data: false });

    const { result } = renderHook(() => usePairedSession("session-1"));

    expect(result.current.phase).toBe("waiting_partner_data");
  });

  it("uses the starting phase when the session is ready", () => {
    liveSession.state = makePairedState();

    const { result } = renderHook(() => usePairedSession("session-1"));

    expect(result.current.phase).toBe("starting");
  });

  it("uses the failed phase when the session start has failed", async () => {
    mockedStartSwipeSession.mockRejectedValueOnce(new Error("Start failed"));
    liveSession.state = makePairedState();

    const { result } = renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.startError).toBe("Unable to start session");
    expect(result.current.phase).toBe("failed");
  });

  it("starts the session when both participants are ready", async () => {
    liveSession.state = makePairedState();

    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedStartSwipeSession).toHaveBeenCalledWith("session-1");
  });

  it("does not start a session when the session ID is missing", async () => {
    liveSession.state = makePairedState();

    renderHook(() => usePairedSession(undefined));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedStartSwipeSession).not.toHaveBeenCalled();
  });

  it("does not start a session when the partner has not joined", async () => {
    liveSession.state = makePairedState({ partner_joined: false });

    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedStartSwipeSession).not.toHaveBeenCalled();
  });

  it("does not start a session when the current user has no data", async () => {
    liveSession.state = makePairedState({ you_have_data: false });

    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedStartSwipeSession).not.toHaveBeenCalled();
  });

  it("does not start a session when the partner has no data", async () => {
    liveSession.state = makePairedState({ partner_has_data: false });

    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedStartSwipeSession).not.toHaveBeenCalled();
  });

  it("does not start a session when the session is already active", async () => {
    liveSession.state = makePairedState({ status: "ACTIVE" });

    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedStartSwipeSession).not.toHaveBeenCalled();
  });

  it("does not start a session when the session is finished", async () => {
    liveSession.state = makePairedState({ status: "FINISHED" });

    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedStartSwipeSession).not.toHaveBeenCalled();
  });

  it("refreshes the session after starting successfully", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    liveSession = makeLiveSessionResult({ state: makePairedState(), refresh });

    mockedUseLiveSession.mockReturnValue(
      liveSession as unknown as ReturnType<typeof useLiveSession>,
    );

    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(refresh).toHaveBeenCalled();
  });

  it("sets the start error when starting fails", async () => {
    mockedStartSwipeSession.mockRejectedValueOnce(new Error("Server error"));
    mockedGetErrorMessage.mockReturnValueOnce("Could not start");

    liveSession.state = makePairedState();

    const { result } = renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.startError).toBe("Could not start");
    expect(result.current.phase).toBe("failed");
  });

  it("delegates fatal start errors to handleFailure", async () => {
    const fatalError = "session_expired" as Parameters<
      typeof mockedClassifyFatalError
    >[0];
    const failure = new Error("Session expired");

    mockedStartSwipeSession.mockRejectedValueOnce(failure);
    mockedClassifyFatalError.mockReturnValue(
      fatalError as ReturnType<typeof classifyFatalError>,
    );

    liveSession.state = makePairedState();

    const handleFailure = vi.fn();
    liveSession.handleFailure = handleFailure;

    mockedUseLiveSession.mockReturnValue(
      liveSession as unknown as ReturnType<typeof useLiveSession>,
    );

    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(handleFailure).toHaveBeenCalledWith(failure);
  });

  it("provides a retry callback that clears the start error and refreshes", () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    liveSession = makeLiveSessionResult({
      state: makePairedState(),
      refresh,
    });

    mockedUseLiveSession.mockReturnValue(
      liveSession as unknown as ReturnType<typeof useLiveSession>,
    );

    const { result } = renderHook(() => usePairedSession("session-1"));

    act(() => {
      result.current.retryStart();
    });

    expect(refresh).toHaveBeenCalled();
    expect(result.current.startError).toBeNull();
  });

  it("calls useHeartbeat with the current waiting state", () => {
    liveSession.state = makePairedState({ status: "WAITING" });

    renderHook(() => usePairedSession("session-1"));

    expect(mockedUseHeartbeat).toHaveBeenCalledWith(
      "session-1",
      true,
      { immediate: true },
    );
  });

  it("disables heartbeat when the session is active", () => {
    liveSession.state = makePairedState({ status: "ACTIVE" });

    renderHook(() => usePairedSession("session-1"));

    expect(mockedUseHeartbeat).toHaveBeenCalledWith(
      "session-1",
      false,
      { immediate: true },
    );
  });

  it("records when the session becomes active", () => {
    const { result, rerender } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onState: (state: PairedSessionState) => unknown;
    };

    act(() => {
      options.onState(makePairedState({ status: "ACTIVE" }));
    });

    rerender();

    expect(result.current.hasBeenActive).toBe(true);
  });

  it("records when the session becomes finished", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onState: (state: PairedSessionState) => unknown;
    };

    act(() => {
      options.onState(makePairedState({ status: "FINISHED" }));
    });

    expect(result.current.ended).toBe(true);
  });

  it("registers a match from a WebSocket event", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onMessage: (
        event: {
          event: string;
          candidate_id?: string;
          title?: string;
          release_year?: number | null;
        },
        refresh: () => Promise<void>,
      ) => void;
    };

    act(() => {
      options.onMessage(
        {
          event: "match",
          candidate_id: "movie-1",
          title: "Example Movie",
          release_year: 2024,
        },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.toast).toEqual({
      candidateId: "movie-1",
      tmdbId: undefined,
      title: "Example Movie",
      releaseYear: 2024,
      posterUrl: null,
    });
  });

  it("does not register duplicate matches", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onMessage: (
        event: {
          event: string;
          candidate_id?: string;
          title?: string;
          release_year?: number | null;
        },
        refresh: () => Promise<void>,
      ) => void;
    };

    const event = {
      event: "match",
      candidate_id: "movie-1",
      title: "Example Movie",
      release_year: 2024,
    };

    act(() => {
      options.onMessage(event, vi.fn().mockResolvedValue(undefined));
      options.onMessage(event, vi.fn().mockResolvedValue(undefined));
    });

    expect(result.current.matchCount).toBe(1);
  });

  it("dismisses a match toast", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onMessage: (
        event: {
          event: string;
          candidate_id?: string;
          title?: string;
          release_year?: number | null;
        },
        refresh: () => Promise<void>,
      ) => void;
    };

    act(() => {
      options.onMessage(
        {
          event: "match",
          candidate_id: "movie-1",
          title: "Example Movie",
          release_year: 2024,
        },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    act(() => {
      result.current.dismissToast();
    });

    expect(result.current.toast).toBeNull();
    expect(result.current.matchCount).toBe(1);
  });

  it("sets partner activity when another participant records a swipe", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onState: (state: PairedSessionState) => unknown;
      onMessage: (
        event: Record<string, unknown>,
        refresh: () => Promise<void>,
      ) => void;
    };

    act(() => {
      options.onState(makePairedState({ current_user_id: "user-1" }));
    });

    act(() => {
      options.onMessage(
        {
          event: "swipe.recorded",
          user_id: "user-2",
          candidate_id: "movie-2",
          action: "WATCHLIST",
          title: "Another Movie",
        },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(result.current.activity).toEqual({
      key: "movie-2",
      action: "WATCHLIST",
      title: "Another Movie",
    });
  });

  it("ignores swipe activity from the current participant", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onState: (state: PairedSessionState) => unknown;
      onMessage: (
        event: Record<string, unknown>,
        refresh: () => Promise<void>,
      ) => void;
    };

    act(() => {
      options.onState(makePairedState({ current_user_id: "user-1" }));
    });

    act(() => {
      options.onMessage(
        {
          event: "swipe.recorded",
          user_id: "user-1",
          candidate_id: "movie-2",
          action: "SKIP",
          title: "Another Movie",
        },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(result.current.activity).toBeNull();
  });

  it("ignores swipe activity when the current user ID is unavailable", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onMessage: (
        event: Record<string, unknown>,
        refresh: () => Promise<void>,
      ) => void;
    };

    act(() => {
      options.onMessage(
        {
          event: "swipe.recorded",
          user_id: "user-2",
          candidate_id: "movie-2",
          action: "SKIP",
          title: "Another Movie",
        },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(result.current.activity).toBeNull();
  });

  it("dismisses partner activity", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onState: (state: PairedSessionState) => unknown;
      onMessage: (
        event: Record<string, unknown>,
        refresh: () => Promise<void>,
      ) => void;
    };

    act(() => {
      options.onState(makePairedState({ current_user_id: "user-1" }));
      options.onMessage(
        {
          event: "swipe.recorded",
          user_id: "user-2",
          candidate_id: "movie-2",
          action: "SKIP",
          title: "Another Movie",
        },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(result.current.activity).not.toBeNull();

    act(() => {
      result.current.dismissActivity();
    });

    expect(result.current.activity).toBeNull();
  });

  it("marks the session ended when an ended update event arrives", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onMessage: (
        event: { event: string; reason?: string },
        refresh: () => Promise<void>,
      ) => void;
    };

    act(() => {
      options.onMessage(
        { event: "session.updated", reason: "ended" },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(result.current.ended).toBe(true);
  });

  it("refreshes state when a session updated event arrives", () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    liveSession = makeLiveSessionResult({ refresh });

    mockedUseLiveSession.mockReturnValue(
      liveSession as unknown as ReturnType<typeof useLiveSession>,
    );

    renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onMessage: (
        event: { event: string; reason?: string },
        refresh: () => Promise<void>,
      ) => void;
    };

    act(() => {
      options.onMessage({ event: "session.updated" }, refresh);
    });

    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("syncs matches when the state reports more matches than currently known", async () => {
    mockedGetSessionMatches
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        makeMatchRecord("movie-1", "Example Movie", 2024),
      ]);

    const { result } = renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onState: (state: PairedSessionState) => unknown;
    };

    await act(async () => {
      options.onState(makePairedState({ matches_count: 1 }));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.matchCount).toBe(1);
  });

  it("uses the state refresh and reload callbacks provided by the live session", () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    const reload = vi.fn();

    liveSession = makeLiveSessionResult({ refresh, reload });

    mockedUseLiveSession.mockReturnValue(
      liveSession as unknown as ReturnType<typeof useLiveSession>,
    );

    const { result } = renderHook(() => usePairedSession("session-1"));

    act(() => {
      result.current.reload();
    });

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("registers bootstrapped matches without showing a toast", async () => {
    mockedGetSessionMatches.mockResolvedValueOnce([
      makeMatchRecord("movie-1", "Example Movie", 2024),
    ]);

    const { result } = renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.toast).toBeNull();
  });

  it("does not sync matches when the session ID becomes unavailable", async () => {
    const { rerender } = renderHook(
      ({ sessionId }: { sessionId: string | undefined }) =>
        usePairedSession(sessionId),
      {
        initialProps: {
          sessionId: "session-1" as string | undefined,
        },
      },
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedGetSessionMatches).toHaveBeenCalledTimes(1);

    rerender({ sessionId: undefined });

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onState: (state: PairedSessionState) => unknown;
    };

    act(() => {
      options.onState(makePairedState({ matches_count: 1 }));
    });

    await act(async () => {
      await Promise.resolve();
    });

    expect(mockedGetSessionMatches).toHaveBeenCalledTimes(1);
  });

  it("does not bootstrap matches a second time after the bootstrap has started", async () => {
    const { rerender } = renderHook(
      ({ sessionId }: { sessionId: string | undefined }) =>
        usePairedSession(sessionId),
      { initialProps: { sessionId: "session-1" } },
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedGetSessionMatches).toHaveBeenCalledTimes(1);

    rerender({ sessionId: "session-2" });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedGetSessionMatches).toHaveBeenCalledTimes(1);
  });

  it("ignores unrecognized socket events", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    const options = mockedUseLiveSession.mock.calls.at(-1)?.[0] as {
      onMessage: (
        event: never,
        refresh: () => Promise<void>,
      ) => void;
    };

    act(() => {
      options.onMessage(
        { event: "unrecognized.event" } as never,
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(result.current.matchCount).toBe(0);
    expect(result.current.toast).toBeNull();
  });

  it("does not start the same ready session twice", async () => {
    liveSession.state = makePairedState();

    const { rerender } = renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockedStartSwipeSession).toHaveBeenCalledTimes(1);

    liveSession.state = makePairedState();

    rerender();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedStartSwipeSession).toHaveBeenCalledTimes(1);
  });

  it("passes the TMDb id of a match event to the toast", () => {
    const { result } = renderHook(() => usePairedSession("session-1"));

    act(() => {
      lastLiveOptions().onMessage(
        {
          event: "match",
          candidate_id: "candidate-1",
          tmdb_id: 550,
          title: "Fight Club",
          release_year: 1999,
        },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(result.current.toast).toEqual({
      candidateId: "candidate-1",
      tmdbId: 550,
      title: "Fight Club",
      releaseYear: 1999,
      posterUrl: null,
    });
  });

  it("syncs matches right after a match event and again after the poster retry delay", async () => {
    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockedGetSessionMatches).toHaveBeenCalledTimes(1);

    act(() => {
      lastLiveOptions().onMessage(
        {
          event: "match",
          candidate_id: "candidate-1",
          tmdb_id: 550,
          title: "Fight Club",
          release_year: 1999,
        },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(mockedGetSessionMatches).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(mockedGetSessionMatches).toHaveBeenCalledTimes(3);
  });

  it("fills in the toast poster once the matches endpoint returns it", async () => {
    mockedGetSessionMatches.mockResolvedValueOnce([]).mockResolvedValue([
      {
        ...makeMatchRecord("candidate-1", "Fight Club", 1999),
        movie: {
          tmdb_id: 550,
          title: "Fight Club",
          release_year: 1999,
          poster_url: "/poster.jpg",
        },
      },
    ]);

    const { result } = renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    act(() => {
      lastLiveOptions().onMessage(
        {
          event: "match",
          candidate_id: "candidate-1",
          tmdb_id: 550,
          title: "Fight Club",
          release_year: 1999,
        },
        vi.fn().mockResolvedValue(undefined),
      );
    });

    expect(result.current.toast?.posterUrl).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.toast?.posterUrl).toBe("/poster.jpg");
    expect(result.current.matchCount).toBe(1);
  });

  it("announces matches discovered after the initial bootstrap", async () => {
    mockedGetSessionMatches
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        makeMatchRecord("candidate-1", "Fight Club", 1999),
      ]);

    const { result } = renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    await act(async () => {
      lastLiveOptions().onState(makePairedState({ matches_count: 1 }));
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.matchCount).toBe(1);
    expect(result.current.toast?.candidateId).toBe("candidate-1");
    expect(result.current.toast?.posterUrl).toBeNull();
  });

  it("does not sync matches from a state update before the bootstrap has finished", () => {
    renderHook(() => usePairedSession("session-1"));

    act(() => {
      lastLiveOptions().onState(makePairedState({ matches_count: 5 }));
    });

    expect(mockedGetSessionMatches).not.toHaveBeenCalled();
  });

  it("does not sync matches when the state reports no new matches", async () => {
    renderHook(() => usePairedSession("session-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    act(() => {
      lastLiveOptions().onState(makePairedState({ matches_count: 0 }));
    });

    expect(mockedGetSessionMatches).toHaveBeenCalledTimes(1);
  });

  it("does not start a session when the live session has a fatal error", async () => {
    liveSession = makeLiveSessionResult({
      state: makePairedState(),
      fatal: "closed",
    });
    mockedUseLiveSession.mockReturnValue(
      liveSession as unknown as ReturnType<typeof useLiveSession>,
    );

    renderHook(() => usePairedSession("session-1"));

    await act(flushAsync);

    expect(mockedStartSwipeSession).not.toHaveBeenCalled();
  });

  it("does not expose a start error when the failure is fatal", async () => {
    const failure = new Error("Session expired");
    const handleFailure = vi.fn();

    mockedStartSwipeSession.mockRejectedValueOnce(failure);
    mockedClassifyFatalError.mockReturnValue(
      "closed" as ReturnType<typeof classifyFatalError>,
    );

    liveSession = makeLiveSessionResult({
      state: makePairedState(),
      handleFailure,
    });
    mockedUseLiveSession.mockReturnValue(
      liveSession as unknown as ReturnType<typeof useLiveSession>,
    );

    const { result } = renderHook(() => usePairedSession("session-1"));

    await act(flushAsync);

    expect(handleFailure).toHaveBeenCalledWith(failure);
    expect(result.current.startError).toBeNull();
  });

  it("starts again after retryStart once a fresh state arrives", async () => {
    mockedStartSwipeSession
      .mockRejectedValueOnce(new Error("Start failed"))
      .mockResolvedValueOnce({} as Awaited<ReturnType<typeof startSwipeSession>>);
    liveSession.state = makePairedState();

    const { result, rerender } = renderHook(() =>
      usePairedSession("session-1"),
    );

    await act(flushAsync);

    expect(mockedStartSwipeSession).toHaveBeenCalledTimes(1);
    expect(result.current.phase).toBe("failed");

    act(() => {
      result.current.retryStart();
    });

    expect(result.current.startError).toBeNull();
    expect(liveSession.refresh).toHaveBeenCalled();

    liveSession.state = makePairedState();
    rerender();

    await act(flushAsync);

    expect(mockedStartSwipeSession).toHaveBeenCalledTimes(2);
  });

  it("can start again after the session stops being ready and becomes ready again", async () => {
    liveSession.state = makePairedState();

    const { rerender } = renderHook(() => usePairedSession("session-1"));

    await act(flushAsync);

    expect(mockedStartSwipeSession).toHaveBeenCalledTimes(1);

    liveSession.state = makePairedState({ partner_has_data: false });
    rerender();

    await act(flushAsync);

    expect(mockedStartSwipeSession).toHaveBeenCalledTimes(1);

    liveSession.state = makePairedState();
    rerender();

    await act(flushAsync);

    expect(mockedStartSwipeSession).toHaveBeenCalledTimes(2);
  });

  it("clears the previous start error when a new start attempt begins", async () => {
    mockedStartSwipeSession
      .mockRejectedValueOnce(new Error("Start failed"))
      .mockResolvedValueOnce({} as Awaited<ReturnType<typeof startSwipeSession>>);
    liveSession.state = makePairedState();

    const { result, rerender } = renderHook(() =>
      usePairedSession("session-1"),
    );

    await act(flushAsync);

    expect(result.current.startError).toBe("Unable to start session");

    liveSession.state = makePairedState({ partner_has_data: false });
    rerender();
    liveSession.state = makePairedState();
    rerender();

    await act(flushAsync);

    expect(mockedStartSwipeSession).toHaveBeenCalledTimes(2);
    expect(result.current.startError).toBeNull();
  });
});