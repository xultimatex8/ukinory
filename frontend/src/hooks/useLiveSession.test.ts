import { act, renderHook } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import {
  classifyFatalError,
  type FatalSessionError,
  type ParticipantState,
} from "../services/sessions";
import { getErrorMessage } from "../utils/errors";
import { getAccessToken } from "../utils/tokens";
import {
  deriveLobbyPhase,
  useLiveSession,
} from "./useLiveSession";

vi.mock("../services/sessions", () => ({
  classifyFatalError: vi.fn(),
}));

vi.mock("../utils/errors", () => ({
  getErrorMessage: vi.fn(),
}));

vi.mock("../utils/tokens", () => ({
  getAccessToken: vi.fn(),
}));

const mockedClassifyFatalError = vi.mocked(classifyFatalError);
const mockedGetErrorMessage = vi.mocked(getErrorMessage);
const mockedGetAccessToken = vi.mocked(getAccessToken);

const originalWebSocket = globalThis.WebSocket;
const originalSessionWs = import.meta.env.VITE_SESSION_WS;

type SocketHandlers = {
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
};

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  readyState = 0;
  onopen: SocketHandlers["onopen"] = null;
  onmessage: SocketHandlers["onmessage"] = null;
  onerror: SocketHandlers["onerror"] = null;
  onclose: SocketHandlers["onclose"] = null;
  close = vi.fn((code = 1000, reason = "") => {
    this.readyState = 3;
    this.onclose?.({
      code,
      reason,
      wasClean: true,
    } as CloseEvent);
  });

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  open() {
    this.readyState = 1;
    this.onopen?.({} as Event);
  }

  message(data: string) {
    this.onmessage?.({ data } as MessageEvent);
  }

  fail() {
    this.onerror?.({} as Event);
  }

  serverClose(code = 1006) {
    this.readyState = 3;
    this.onclose?.({
      code,
      reason: "",
      wasClean: false,
    } as CloseEvent);
  }
}

function makeParticipantState(
  overrides: Partial<ParticipantState> = {},
): ParticipantState {
  return {
    partner_joined: true,
    you_have_data: true,
    partner_has_data: true,
    ...overrides,
  } as ParticipantState;
}

describe("deriveLobbyPhase", () => {
  it("returns loading when no state is available", () => {
    expect(deriveLobbyPhase(null)).toBe("loading");
  });

  it("returns waiting_partner when the partner has not joined", () => {
    expect(
      deriveLobbyPhase(makeParticipantState({ partner_joined: false })),
    ).toBe("waiting_partner");
  });

  it("returns needs_import when the current participant has no data", () => {
    expect(
      deriveLobbyPhase(makeParticipantState({ you_have_data: false })),
    ).toBe("needs_import");
  });

  it("returns waiting_partner_data when the partner has no data", () => {
    expect(
      deriveLobbyPhase(makeParticipantState({ partner_has_data: false })),
    ).toBe("waiting_partner_data");
  });

  it("returns null when both participants are ready", () => {
    expect(deriveLobbyPhase(makeParticipantState())).toBeNull();
  });

  it("prioritizes waiting for the partner before data checks", () => {
    expect(
      deriveLobbyPhase(
        makeParticipantState({
          partner_joined: false,
          you_have_data: false,
          partner_has_data: false,
        }),
      ),
    ).toBe("waiting_partner");
  });
});

describe("useLiveSession", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    MockWebSocket.instances = [];

    mockedClassifyFatalError.mockReturnValue(null);
    mockedGetErrorMessage.mockReturnValue("Request failed");
    mockedGetAccessToken.mockReturnValue(null as never);

    vi.stubGlobal("WebSocket", MockWebSocket);
    import.meta.env.VITE_SESSION_WS = "false";
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    import.meta.env.VITE_SESSION_WS = originalSessionWs;
    globalThis.WebSocket = originalWebSocket;
  });

  it("initializes with an empty state", () => {
    const fetchState = vi.fn().mockResolvedValue({ value: 1 });
    const socketUrl = vi.fn().mockReturnValue("ws://localhost/session");

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl,
      }),
    );

    expect(result.current.state).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.fatal).toBeNull();
    expect(result.current.socketConnected).toBe(false);
  });

  it("fetches the initial state asynchronously", async () => {
    const state = { value: 1 };
    const fetchState = vi.fn().mockResolvedValue(state);

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(fetchState).toHaveBeenCalledWith("session-1");
    expect(result.current.state).toEqual(state);
    expect(result.current.error).toBeNull();
  });

  it("does not fetch when the session ID is missing", async () => {
    const fetchState = vi.fn().mockResolvedValue({ value: 1 });

    renderHook(() =>
      useLiveSession({
        sessionId: undefined,
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(fetchState).not.toHaveBeenCalled();
  });

  it("does not fetch when disabled", async () => {
    const fetchState = vi.fn().mockResolvedValue({ value: 1 });

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
        enabled: false,
      }),
    );

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(fetchState).not.toHaveBeenCalled();
  });

  it("refreshes state and clears a previous error on success", async () => {
    const state = { value: 2 };
    const fetchState = vi.fn().mockResolvedValue(state);

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    act(() => {
      result.current.setError("Previous error");
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.state).toEqual(state);
    expect(result.current.error).toBeNull();
  });

  it("sets an error when the initial fetch fails", async () => {
    const failure = new Error("Network failure");
    const fetchState = vi.fn().mockRejectedValue(failure);

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    await act(async () => {
      await result.current.refresh();
    });

    expect(mockedGetErrorMessage).toHaveBeenCalledWith(failure);
    expect(result.current.error).toBe("Request failed");
  });

  it("silently handles non-fatal errors after a successful load", async () => {
    const fetchState = vi
      .fn()
      .mockResolvedValueOnce({ value: 1 })
      .mockRejectedValueOnce(new Error("Temporary failure"));

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.state).toEqual({ value: 1 });

    act(() => {
      result.current.setError(null);
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.error).toBeNull();
  });

  it("sets a fatal error when the request fails with a fatal condition", async () => {
    const fatalKind = "session_expired" as FatalSessionError;
    const failure = new Error("Session expired");

    mockedClassifyFatalError.mockReturnValue(fatalKind);

    const fetchState = vi.fn().mockRejectedValue(failure);

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.fatal).toBe(fatalKind);
    expect(result.current.error).toBeNull();
  });

  it("sets a fatal error returned by onState", async () => {
    const fatalKind = "session_expired" as FatalSessionError;
    const state = { value: 1 };
    const fetchState = vi.fn().mockResolvedValue(state);
    const onState = vi.fn().mockReturnValue(fatalKind);

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
        onState,
      }),
    );

    await act(async () => {
      await result.current.refresh();
    });

    expect(onState).toHaveBeenCalledWith(state);
    expect(result.current.state).toEqual(state);
    expect(result.current.fatal).toBe(fatalKind);
  });

  it("does not set an error when onState returns no fatal condition", async () => {
    const state = { value: 1 };
    const onState = vi.fn().mockReturnValue(undefined);

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue(state),
        socketUrl: () => "ws://localhost/session",
        onState,
      }),
    );

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.state).toEqual(state);
    expect(result.current.fatal).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("does not refresh when the session ID is missing", async () => {
    const fetchState = vi.fn();

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: undefined,
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    await act(async () => {
      await result.current.refresh();
    });

    expect(fetchState).not.toHaveBeenCalled();
  });

  it("reloads by clearing the error and fatal state and refreshing", async () => {
    const fetchState = vi.fn().mockResolvedValue({ value: 3 });

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    act(() => {
      result.current.setError("Old error");
      result.current.handleFailure(new Error("Fatal"));
    });

    await act(async () => {
      result.current.reload();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.fatal).toBeNull();
    expect(result.current.state).toEqual({ value: 3 });
  });

  it("uses the latest fetchState callback without restarting the hook", async () => {
    const firstFetch = vi.fn().mockResolvedValue({ source: "first" });
    const secondFetch = vi.fn().mockResolvedValue({ source: "second" });

    const { result, rerender } = renderHook(
      ({ fetchState }: { fetchState: (id: string) => Promise<unknown> }) =>
        useLiveSession({
          sessionId: "session-1",
          fetchState,
          socketUrl: () => "ws://localhost/session",
        }),
      { initialProps: { fetchState: firstFetch } },
    );

    rerender({ fetchState: secondFetch });

    await act(async () => {
      await result.current.refresh();
    });

    expect(firstFetch).not.toHaveBeenCalled();
    expect(secondFetch).toHaveBeenCalledWith("session-1");
    expect(result.current.state).toEqual({ source: "second" });
  });

  it("polls faster while the socket is disconnected", async () => {
    const fetchState = vi.fn().mockResolvedValue({ value: 1 });

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetchState).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(fetchState).toHaveBeenCalledTimes(2);
  });

  it("stops polling when disabled", async () => {
    const fetchState = vi.fn().mockResolvedValue({ value: 1 });

    const { rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useLiveSession({
          sessionId: "session-1",
          fetchState,
          socketUrl: () => "ws://localhost/session",
          enabled,
        }),
      { initialProps: { enabled: true } },
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const callsBeforeDisable = fetchState.mock.calls.length;

    rerender({ enabled: false });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(fetchState).toHaveBeenCalledTimes(callsBeforeDisable);
  });

  it("creates a WebSocket when socket support is enabled and a token exists", async () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: (id, token) => `ws://localhost/${id}?token=${token}`,
      }),
    );

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe(
      "ws://localhost/session-1?token=test-token",
    );
  });

  it("does not create a WebSocket when no access token exists", () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue(null as never);

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: () => "ws://localhost/session",
      }),
    );

    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it("marks the socket as connected when it opens", async () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    const { result } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: () => "ws://localhost/session",
      }),
    );

    act(() => {
      MockWebSocket.instances[0].open();
    });

    expect(result.current.socketConnected).toBe(true);
  });

  it("parses WebSocket messages and passes them to onMessage", () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    const onMessage = vi.fn();

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: () => "ws://localhost/session",
        onMessage,
      }),
    );

    act(() => {
      MockWebSocket.instances[0].message('{"type":"updated"}');
    });

    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onMessage).toHaveBeenCalledWith(
      { type: "updated" },
      expect.any(Function),
    );
  });

  it("ignores malformed WebSocket messages", () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    const onMessage = vi.fn();

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: () => "ws://localhost/session",
        onMessage,
      }),
    );

    act(() => {
      MockWebSocket.instances[0].message("not-json");
    });

    expect(onMessage).not.toHaveBeenCalled();
  });

  it("refreshes state when a WebSocket message arrives without a handler", async () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    const fetchState = vi.fn().mockResolvedValue({ value: 1 });

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState,
        socketUrl: () => "ws://localhost/session",
      }),
    );

    const socket = MockWebSocket.instances[0];
    expect(socket).toBeDefined();

    act(() => {
      socket.message('{"type":"updated"}');
    });

    expect(fetchState).toHaveBeenCalledWith("session-1");

    await act(async () => {
      await Promise.resolve();
    });
  });

  it("closes the socket when a socket error occurs", () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: () => "ws://localhost/session",
      }),
    );

    const socket = MockWebSocket.instances[0];

    act(() => {
      socket.fail();
    });

    expect(socket.close).toHaveBeenCalledTimes(1);
  });

  it("does not retry after an unauthenticated close", async () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: () => "ws://localhost/session",
      }),
    );

    act(() => {
      MockWebSocket.instances[0].serverClose(4401);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });

    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("does not retry after a forbidden close", async () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: () => "ws://localhost/session",
      }),
    );

    act(() => {
      MockWebSocket.instances[0].serverClose(4403);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });

    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("retries the WebSocket after an unexpected close", async () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: () => "ws://localhost/session",
      }),
    );

    act(() => {
      MockWebSocket.instances[0].serverClose(1006);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("closes the socket when the hook unmounts", () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    const { unmount } = renderHook(() =>
      useLiveSession({
        sessionId: "session-1",
        fetchState: vi.fn().mockResolvedValue({ value: 1 }),
        socketUrl: () => "ws://localhost/session",
      }),
    );

    const socket = MockWebSocket.instances[0];

    unmount();

    expect(socket.close).toHaveBeenCalled();
  });

  it("uses the latest onMessage callback after rerender", () => {
    import.meta.env.VITE_SESSION_WS = "true";
    mockedGetAccessToken.mockReturnValue("test-token" as never);

    const firstHandler = vi.fn();
    const secondHandler = vi.fn();

    const { rerender } = renderHook(
      ({ onMessage }: { onMessage: (event: unknown, refresh: () => Promise<void>) => void }) =>
        useLiveSession({
          sessionId: "session-1",
          fetchState: vi.fn().mockResolvedValue({ value: 1 }),
          socketUrl: () => "ws://localhost/session",
          onMessage,
        }),
      { initialProps: { onMessage: firstHandler } },
    );

    rerender({ onMessage: secondHandler });

    act(() => {
      MockWebSocket.instances[0].message('{"type":"updated"}');
    });

    expect(firstHandler).not.toHaveBeenCalled();
    expect(secondHandler).toHaveBeenCalledTimes(1);
  });
});