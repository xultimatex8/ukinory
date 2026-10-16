import { useEffect } from "react";

import { sendHeartbeat } from "../services/swipeSessions";

export const HEARTBEAT_INTERVAL_MS = 20_000;

export function useHeartbeat(
  sessionId: string | undefined,
  enabled: boolean,
  { immediate = false }: { immediate?: boolean } = {},
) {
  useEffect(() => {
    if (!sessionId || !enabled) return;

    if (immediate) {
      void sendHeartbeat(sessionId);
    }

    const interval = window.setInterval(
      () => void sendHeartbeat(sessionId),
      HEARTBEAT_INTERVAL_MS,
    );

    return () => window.clearInterval(interval);
  }, [sessionId, enabled, immediate]);
}