import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../services/api";
import {
  buildRoomSocketUrl,
  generateComparison,
  getComparisonResult,
  getRoom,
  type ComparisonResult,
  type RoomState,
} from "../services/comparisons";
import { getErrorMessage } from "../utils/errors";

export type RoomPhase =
  | "loading"
  | "waiting_partner"
  | "needs_import"
  | "waiting_partner_data"
  | "generating"
  | "failed"
  | "ready";

export type FatalRoomError = "not_found" | "forbidden" | null;

const POLL_FAST_MS = 3000;
const POLL_SLOW_MS = 15000;
const MAX_RECONNECT_MS = 15000;
const SOCKET_ENABLED = import.meta.env.VITE_COMPARISON_WS !== "false";

function derivePhase(
  room: RoomState | null,
  result: ComparisonResult | null,
): RoomPhase {
  if (result) return "ready";
  if (!room) return "loading";
  if (!room.partner_joined) return "waiting_partner";
  if (!room.you_have_data) return "needs_import";
  if (room.partner_has_data === false) return "waiting_partner_data";
  if (room.generation_status === "failed") return "failed";
  return "generating";
}

export function useComparisonRoom(roomId: string | undefined) {
  const [room, setRoom] = useState<RoomState | null>(null);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fatal, setFatal] = useState<FatalRoomError>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [socketConnected, setSocketConnected] = useState(false);

  const roomLoadedRef = useRef(false);
  const generatingRef = useRef(false);
  const lastKickKeyRef = useRef<string | null>(null);

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

  const refresh = useCallback(async () => {
    if (!roomId) return;

    try {
      const state = await getRoom(roomId);

      roomLoadedRef.current = true;
      setRoom(state);
      setError(null);
    } catch (err) {
      handleFailure(err, roomLoadedRef.current);
    }
  }, [roomId, handleFailure]);

  const kickGeneration = useCallback(async () => {
    if (!roomId || generatingRef.current) return;

    generatingRef.current = true;
    setIsGenerating(true);

    try {
      setRoom(await generateComparison(roomId));
      setError(null);
    } catch (err) {
      handleFailure(err);
    } finally {
      generatingRef.current = false;
      setIsGenerating(false);
    }
  }, [roomId, handleFailure]);

  useEffect(() => {
    if (!roomId || fatal || result) return;

    const initialRefreshTimer = window.setTimeout(() => {
      void refresh();
    }, 0);

    const timer = window.setInterval(
      () => void refresh(),
      socketConnected ? POLL_SLOW_MS : POLL_FAST_MS,
    );

    return () => {
      window.clearTimeout(initialRefreshTimer);
      window.clearInterval(timer);
    };
  }, [roomId, fatal, result, socketConnected, refresh]);

  useEffect(() => {
    if (!SOCKET_ENABLED || !roomId || fatal || result) return;

    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let attempts = 0;
    let disposed = false;

    const connect = () => {
      const token = localStorage.getItem("access_token");

      if (!token || disposed) return;

      socket = new WebSocket(buildRoomSocketUrl(roomId, token));

      socket.onopen = () => {
        attempts = 0;
        setSocketConnected(true);
      };

      socket.onmessage = () => void refresh();

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
  }, [roomId, fatal, result, refresh]);

  useEffect(() => {
    if (!roomId || !room || result || fatal) return;

    const bothReady =
      room.status === "ACTIVE" &&
      room.partner_joined &&
      room.you_have_data &&
      room.partner_has_data === true;

    const needsKick =
      room.generation_status === "pending" ||
      room.generation_status === "needs_data";

    if (!bothReady || !needsKick) return;

    const key = `${room.generation_status}|${room.you_have_data}|${room.partner_has_data}`;

    if (lastKickKeyRef.current === key) return;

    lastKickKeyRef.current = key;

    void kickGeneration();
  }, [roomId, room, result, fatal, kickGeneration]);

  useEffect(() => {
    if (!roomId || result || room?.generation_status !== "ready") {
      return;
    }

    let cancelled = false;

    getComparisonResult(roomId)
      .then((data) => {
        if (!cancelled) {
          setResult(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          handleFailure(err);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [roomId, room?.generation_status, result, handleFailure]);

  const reload = useCallback(() => {
    setError(null);
    void refresh();
  }, [refresh]);

  const retryGeneration = useCallback(() => {
    setError(null);
    lastKickKeyRef.current = null;
    void kickGeneration();
  }, [kickGeneration]);

  return {
    room,
    result,
    phase: derivePhase(room, result),
    error,
    fatal,
    isGenerating,
    refresh,
    reload,
    retryGeneration,
  };
}