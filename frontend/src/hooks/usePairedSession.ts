import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../services/api";
import {
  buildSessionSocketUrl,
  getPairedSessionState,
  getSessionMatches,
  sendHeartbeat,
  startSwipeSession,
  type MatchEvent,
  type PairedSessionState,
} from "../services/swipeSessions";
import { getErrorMessage } from "../utils/errors";

export type PairedPhase =
  | "loading"
  | "waiting_partner"
  | "needs_import"
  | "waiting_partner_data"
  | "starting"
  | "failed"
  | "active"
  | "closed";

export type FatalPairedError = "not_found" | "forbidden" | null;

export interface MatchToast {
  candidateId: string;
  title: string;
  releaseYear: number | null;
}

export interface PartnerActivity {
  key: string;
  action: "SKIP" | "WATCHLIST";
  title: string;
}

type PairedSocketEvent =
  | { event: "session.updated"; reason?: string }
  | {
      event: "swipe.recorded";
      user_id: string;
      candidate_id: string;
      action: "SKIP" | "WATCHLIST";
      title: string;
      release_year: number | null;
    }
  | ({ event: "match" } & MatchEvent);

const POLL_FAST_MS = 3000;
const POLL_SLOW_MS = 15000;
const MAX_RECONNECT_MS = 15000;
const HEARTBEAT_INTERVAL_MS = 20_000;
const SOCKET_ENABLED = import.meta.env.VITE_PAIRED_SWIPE_WS !== "false";

function derivePhase(
  state: PairedSessionState | null,
  startError: string | null,
): PairedPhase {
  if (!state) return "loading";
  if (state.status === "ACTIVE") return "active";
  if (state.status === "FINISHED") return "closed";
  if (!state.partner_joined) return "waiting_partner";
  if (!state.you_have_data) return "needs_import";
  if (state.partner_has_data === false) return "waiting_partner_data";
  if (startError) return "failed";
  return "starting";
}

export function usePairedSession(sessionId: string | undefined) {
  const [state, setState] = useState<PairedSessionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fatal, setFatal] = useState<FatalPairedError>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [socketConnected, setSocketConnected] = useState(false);
  const [hasBeenActive, setHasBeenActive] = useState(false);
  const [ended, setEnded] = useState(false);
  const [matchCount, setMatchCount] = useState(0);
  const [toast, setToast] = useState<MatchToast | null>(null);
  const [activity, setActivity] = useState<PartnerActivity | null>(null);

  const stateRef = useRef<PairedSessionState | null>(null);
  const loadedRef = useRef(false);
  const startingRef = useRef(false);
  const lastStartKeyRef = useRef<string | null>(null);
  const knownMatchesRef = useRef<Set<string>>(new Set());
  const matchesBootstrappedRef = useRef(false);
  const bootstrapStartedRef = useRef(false);

  const handleFailure = useCallback((err: unknown, silent = false) => {
    if (err instanceof ApiError) {
      if (err.status === 404) {
        setFatal("not_found");
        return;
      }

      if (err.status === 403) {
        setFatal("forbidden");
        return;
      }
    }

    if (!silent) {
      setError(getErrorMessage(err));
    }
  }, []);

  const registerMatch = useCallback((match: MatchToast, announce: boolean) => {
    if (knownMatchesRef.current.has(match.candidateId)) return;

    knownMatchesRef.current.add(match.candidateId);
    setMatchCount(knownMatchesRef.current.size);

    if (announce) {
      setToast(match);
    }
  }, []);

  const syncMatches = useCallback(async () => {
    if (!sessionId) return;

    try {
      const list = await getSessionMatches(sessionId);
      const announce = matchesBootstrappedRef.current;

      [...list].reverse().forEach((item) =>
        registerMatch(
          {
            candidateId: item.candidate_id,
            title: item.movie.title,
            releaseYear: item.movie.release_year,
          },
          announce,
        ),
      );

      matchesBootstrappedRef.current = true;
    } catch {
      // Not critical: the next poll or event retries.
    }
  }, [sessionId, registerMatch]);

  const refresh = useCallback(async () => {
    if (!sessionId) return;

    try {
      const next = await getPairedSessionState(sessionId);

      loadedRef.current = true;
      stateRef.current = next;
      setState(next);
      setError(null);

      if (next.status === "ACTIVE") setHasBeenActive(true);
      if (next.status === "FINISHED") setEnded(true);

      if (
        matchesBootstrappedRef.current &&
        next.matches_count > knownMatchesRef.current.size
      ) {
        void syncMatches();
      }
    } catch (err) {
      handleFailure(err, loadedRef.current);
    }
  }, [sessionId, handleFailure, syncMatches]);

  useEffect(() => {
    if (!sessionId) return;

    const timer = window.setTimeout(() => {
      if (bootstrapStartedRef.current) return;
      bootstrapStartedRef.current = true;
      void syncMatches();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [sessionId, syncMatches]);

  useEffect(() => {
    if (!sessionId || fatal || ended) return;

    const initialTimer = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(
      () => void refresh(),
      socketConnected ? POLL_SLOW_MS : POLL_FAST_MS,
    );

    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [sessionId, fatal, ended, socketConnected, refresh]);

  useEffect(() => {
    if (!SOCKET_ENABLED || !sessionId || fatal || ended) return;

    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let attempts = 0;
    let disposed = false;

    const handleMessage = (raw: MessageEvent) => {
      let data: PairedSocketEvent;

      try {
        data = JSON.parse(raw.data) as PairedSocketEvent;
      } catch {
        return;
      }

      if (data.event === "session.updated") {
        if (data.reason === "ended") setEnded(true);
        void refresh();
        return;
      }

      if (data.event === "swipe.recorded") {
        const me = stateRef.current?.current_user_id;
        if (!me || data.user_id === me) return;

        setActivity({
          key: `${data.candidate_id}`,
          action: data.action,
          title: data.title,
        });
        return;
      }

      if (data.event === "match") {
        registerMatch(
          {
            candidateId: data.candidate_id,
            title: data.title,
            releaseYear: data.release_year,
          },
          true,
        );
      }
    };

    const connect = () => {
      const token = localStorage.getItem("access_token");

      if (!token || disposed) return;

      socket = new WebSocket(buildSessionSocketUrl(sessionId, token));

      socket.onopen = () => {
        attempts = 0;
        setSocketConnected(true);
      };

      socket.onmessage = handleMessage;

      socket.onerror = () => socket?.close();

      socket.onclose = (event) => {
        if (disposed) return;

        setSocketConnected(false);

        if (event.code === 4401 || event.code === 4403) {
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
  }, [sessionId, fatal, ended, refresh, registerMatch]);

  useEffect(() => {
    if (!sessionId || !state || fatal) return;

    const ready =
      state.status === "WAITING" &&
      state.partner_joined &&
      state.you_have_data &&
      state.partner_has_data === true;

    if (!ready) return;

    const key = `${state.you_have_data}|${state.partner_has_data}`;

    if (lastStartKeyRef.current === key || startingRef.current) return;

    const timer = window.setTimeout(() => {
      lastStartKeyRef.current = key;
      startingRef.current = true;
      setStartError(null);

      startSwipeSession(sessionId)
        .then(() => refresh())
        .catch((err) => {
          if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
            handleFailure(err);
            return;
          }

          setStartError(getErrorMessage(err));
        })
        .finally(() => {
          startingRef.current = false;
        });
    }, 0);

    return () => window.clearTimeout(timer);
  }, [sessionId, state, fatal, refresh, handleFailure]);

  const isWaiting = state?.status === "WAITING";

  useEffect(() => {
    if (!sessionId || !isWaiting) return;

    void sendHeartbeat(sessionId);
    const interval = window.setInterval(
      () => void sendHeartbeat(sessionId),
      HEARTBEAT_INTERVAL_MS,
    );

    return () => window.clearInterval(interval);
  }, [sessionId, isWaiting]);

  const retryStart = useCallback(() => {
    setStartError(null);
    lastStartKeyRef.current = null;
    void refresh();
  }, [refresh]);

  const reload = useCallback(() => {
    setError(null);
    setFatal(null);
    void refresh();
  }, [refresh]);

  const dismissToast = useCallback(() => setToast(null), []);
  const dismissActivity = useCallback(() => setActivity(null), []);

  return {
    state,
    phase: derivePhase(state, startError),
    error,
    fatal,
    startError,
    socketConnected,
    hasBeenActive,
    ended,
    matchCount,
    toast,
    activity,
    dismissToast,
    dismissActivity,
    refresh,
    retryStart,
    reload,
  };
}

export type PairedSessionController = ReturnType<typeof usePairedSession>;