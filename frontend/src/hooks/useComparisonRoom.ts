import { useCallback, useEffect, useRef, useState } from "react";

import {
  buildRoomSocketUrl,
  generateComparison,
  getComparisonResult,
  getRoom,
  type ComparisonResult,
  type RoomState,
} from "../services/comparisons";
import type { FatalSessionError } from "../services/sessions";
import {
  deriveLobbyPhase,
  useLiveSession,
  type LobbyPhase,
} from "./useLiveSession";

export type RoomPhase = LobbyPhase | "generating" | "failed" | "ready";

export type FatalRoomError = FatalSessionError | null;

function derivePhase(
  room: RoomState | null,
  result: ComparisonResult | null,
): RoomPhase {
  if (result) return "ready";

  const lobbyPhase = deriveLobbyPhase(room);

  if (lobbyPhase) return lobbyPhase;
  if (room?.generation_status === "failed") return "failed";
  return "generating";
}

const closeWhenFinished = (room: RoomState): FatalSessionError | undefined =>
  room.status === "FINISHED"
    ? "closed"
    : undefined;

export function useComparisonRoom(roomId: string | undefined) {
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const generatingRef = useRef(false);
  const lastKickKeyRef = useRef<string | null>(null);

  const {
    state: room,
    setState: setRoom,
    error,
    setError,
    fatal,
    refresh,
    reload,
    handleFailure,
  } = useLiveSession<RoomState>({
    sessionId: roomId,
    fetchState: getRoom,
    socketUrl: buildRoomSocketUrl,
    // Stays enabled once the result is loaded so a partner leaving is noticed.
    onState: closeWhenFinished,
  });

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
  }, [roomId, setRoom, setError, handleFailure]);

  useEffect(() => {
    if (!roomId || !room || result || fatal) return;

    const bothReady =
      room.status !== "FINISHED" &&
      room.partner_joined &&
      room.you_have_data &&
      room.partner_has_data === true;

    const needsKick =
      room.generation_status === null ||
      room.generation_status === "pending" ||
      room.generation_status === "needs_data";

    if (!bothReady || !needsKick) {
      if (!bothReady) lastKickKeyRef.current = null;
      return;
    }

    const key = `${room.generation_status}|${room.you_have_data}|${room.partner_has_data}`;

    if (lastKickKeyRef.current === key) return;

    lastKickKeyRef.current = key;

    void kickGeneration();
  }, [roomId, room, result, fatal, kickGeneration]);

  useEffect(() => {
    if (!roomId || result || fatal || room?.generation_status !== "ready") {
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
  }, [roomId, room?.generation_status, result, fatal, handleFailure]);

  const retryGeneration = useCallback(() => {
    setError(null);
    lastKickKeyRef.current = null;
    void kickGeneration();
  }, [setError, kickGeneration]);

  return {
    room,
    result,
    phase: derivePhase(room, result),
    roomClosed: room?.status === "FINISHED",
    error,
    fatal,
    isGenerating,
    refresh,
    reload,
    retryGeneration,
  };
}