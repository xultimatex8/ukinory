import { useEffect } from "react";

import { sendHeartbeat } from "../services/swipeSessions";

const HEARTBEAT_INTERVAL_MS = 20_000;

interface UseSwipeSessionLifecycleParams {
  id: string | undefined;
  finished: boolean;
  error: string | null;
}

export function useSwipeSessionLifecycle({
  id,
  finished,
  error,
}: UseSwipeSessionLifecycleParams) {
  useEffect(() => {
    if (!id || finished || error) return;

    const sessionId = id;

    const interval = setInterval(() => {
      void sendHeartbeat(sessionId);
    }, HEARTBEAT_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [id, finished, error]);
}