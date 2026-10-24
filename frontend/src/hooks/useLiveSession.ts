import { useCallback, useEffect, useRef, useState } from "react";

import {
  classifyFatalError,
  type FatalSessionError,
  type ParticipantState,
} from "../services/sessions";
import { getErrorMessage } from "../utils/errors";
import { getAccessToken } from "../utils/tokens";

const POLL_FAST_MS = 3000;
const POLL_SLOW_MS = 15000;
const MAX_RECONNECT_MS = 15000;
const SOCKET_ENABLED = import.meta.env.VITE_SESSION_WS !== "false";

const WS_CLOSE_UNAUTHENTICATED = 4401;
const WS_CLOSE_FORBIDDEN = 4403;

export type LobbyPhase =
  | "loading"
  | "waiting_partner"
  | "needs_import"
  | "waiting_partner_data";

export function deriveLobbyPhase(
  state: ParticipantState | null,
): LobbyPhase | null {
  if (!state) return "loading";
  if (!state.partner_joined) return "waiting_partner";
  if (!state.you_have_data) return "needs_import";
  if (state.partner_has_data === false) return "waiting_partner_data";
  return null;
}

interface UseLiveSessionOptions<S, E> {
  sessionId: string | undefined;
  fetchState: (sessionId: string) => Promise<S>;
  socketUrl: (sessionId: string, token: string) => string;
  enabled?: boolean;
  onState?: (state: S) => FatalSessionError | void;
  onMessage?: (event: E, refresh: () => Promise<void>) => void;
}

export function useLiveSession<S, E = unknown>({
  sessionId,
  fetchState,
  socketUrl,
  enabled = true,
  onState,
  onMessage,
}: UseLiveSessionOptions<S, E>) {
  const [state, setState] = useState<S | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fatal, setFatal] = useState<FatalSessionError | null>(null);
  const [socketConnected, setSocketConnected] = useState(false);

  const loadedRef = useRef(false);

  const fetchStateRef = useRef(fetchState);
  const socketUrlRef = useRef(socketUrl);
  const onStateRef = useRef(onState);
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    fetchStateRef.current = fetchState;
    socketUrlRef.current = socketUrl;
    onStateRef.current = onState;
    onMessageRef.current = onMessage;
  });

  const handleFailure = useCallback((err: unknown, silent = false) => {
    const fatalKind = classifyFatalError(err);

    if (fatalKind) {
      setFatal(fatalKind);
      return;
    }

    if (!silent) {
      setError(getErrorMessage(err));
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!sessionId) return;

    try {
      const next = await fetchStateRef.current(sessionId);

      loadedRef.current = true;
      setState(next);

      const fatalKind = onStateRef.current?.(next);

      if (fatalKind) {
        setFatal(fatalKind);
        return;
      }

      setError(null);
    } catch (err) {
      handleFailure(err, loadedRef.current);
    }
  }, [sessionId, handleFailure]);

  useEffect(() => {
    if (!sessionId || fatal || !enabled) return;

    const initialTimer = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(
      () => void refresh(),
      socketConnected ? POLL_SLOW_MS : POLL_FAST_MS,
    );

    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [sessionId, fatal, enabled, socketConnected, refresh]);

  useEffect(() => {
    if (!SOCKET_ENABLED || !sessionId || fatal || !enabled) return;

    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let attempts = 0;
    let disposed = false;

    const handleMessage = (raw: MessageEvent) => {
      let data: E;

      try {
        data = JSON.parse(raw.data) as E;
      } catch {
        return;
      }

      const handler = onMessageRef.current;

      if (handler) {
        handler(data, refresh);
      } else {
        void refresh();
      }
    };

    const connect = () => {
      const token = getAccessToken();

      if (!token || disposed) return;

      socket = new WebSocket(socketUrlRef.current(sessionId, token));

      socket.onopen = () => {
        attempts = 0;
        setSocketConnected(true);
      };

      socket.onmessage = handleMessage;

      socket.onerror = () => socket?.close();

      socket.onclose = (event) => {
        if (disposed) return;

        setSocketConnected(false);

        if (
          event.code === WS_CLOSE_UNAUTHENTICATED ||
          event.code === WS_CLOSE_FORBIDDEN
        ) {
          return;
        }

        attempts += 1;

        retryTimer = window.setTimeout(
          connect,
          Math.min(1000 * 2 ** attempts, MAX_RECONNECT_MS),
        );
      };
    };

    connect();

    return () => {
      disposed = true;
      window.clearTimeout(retryTimer);
      socket?.close();
      setSocketConnected(false);
    };
  }, [sessionId, fatal, enabled, refresh]);

  const reload = useCallback(() => {
    setError(null);
    setFatal(null);
    void refresh();
  }, [refresh]);

  return {
    state,
    setState,
    error,
    setError,
    fatal,
    socketConnected,
    refresh,
    reload,
    handleFailure,
  };
}