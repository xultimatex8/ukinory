import { useCallback, useEffect, useRef, useState } from "react";

import {
  buildSessionSocketUrl,
  getPairedSessionState,
  getSessionMatches,
  startSwipeSession,
  type MatchEvent,
  type PairedSessionState,
} from "../services/swipeSessions";
import { classifyFatalError, type FatalSessionError } from "../services/sessions";
import { getErrorMessage } from "../utils/errors";
import { useHeartbeat } from "./useHeartbeat";
import {
  deriveLobbyPhase,
  useLiveSession,
  type LobbyPhase,
} from "./useLiveSession";

export type PairedPhase =
  | LobbyPhase
  | "starting"
  | "failed"
  | "active"
  | "closed";

export type FatalPairedError = FatalSessionError | null;

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

function derivePhase(
  state: PairedSessionState | null,
  startError: string | null,
): PairedPhase {
  if (!state) return "loading";
  if (state.status === "ACTIVE") return "active";
  if (state.status === "FINISHED") return "closed";

  const lobbyPhase = deriveLobbyPhase(state);

  if (lobbyPhase) return lobbyPhase;
  if (startError) return "failed";
  return "starting";
}

export function usePairedSession(sessionId: string | undefined) {
  const [startError, setStartError] = useState<string | null>(null);
  const [hasBeenActive, setHasBeenActive] = useState(false);
  const [ended, setEnded] = useState(false);
  const [matchCount, setMatchCount] = useState(0);
  const [toast, setToast] = useState<MatchToast | null>(null);
  const [activity, setActivity] = useState<PartnerActivity | null>(null);

  const stateRef = useRef<PairedSessionState | null>(null);
  const startingRef = useRef(false);
  const lastStartKeyRef = useRef<string | null>(null);
  const knownMatchesRef = useRef<Set<string>>(new Set());
  const matchesBootstrappedRef = useRef(false);
  const bootstrapStartedRef = useRef(false);

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

  const handleState = useCallback(
    (next: PairedSessionState) => {
      stateRef.current = next;

      if (next.status === "ACTIVE") setHasBeenActive(true);
      if (next.status === "FINISHED") setEnded(true);

      if (
        matchesBootstrappedRef.current &&
        next.matches_count > knownMatchesRef.current.size
      ) {
        void syncMatches();
      }
    },
    [syncMatches],
  );

  const handleMessage = useCallback(
    (data: PairedSocketEvent, refresh: () => Promise<void>) => {
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
    },
    [registerMatch],
  );

  const {
    state,
    error,
    fatal,
    socketConnected,
    refresh,
    reload,
    handleFailure,
  } = useLiveSession<PairedSessionState, PairedSocketEvent>({
    sessionId,
    fetchState: getPairedSessionState,
    socketUrl: buildSessionSocketUrl,
    enabled: !ended,
    onState: handleState,
    onMessage: handleMessage,
  });

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
          if (classifyFatalError(err)) {
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

  useHeartbeat(sessionId, state?.status === "WAITING", { immediate: true });

  const retryStart = useCallback(() => {
    setStartError(null);
    lastStartKeyRef.current = null;
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