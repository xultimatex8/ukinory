import { useEffect } from "react";

import {
  getSwipeSession,
  sendHeartbeat,
} from "../services/swipeSessions";

const HEARTBEAT_INTERVAL_MS = 20_000;

interface UseSwipeSessionLifecycleParams {
  id: string | undefined;
  leaveToken: string | null;
  finished: boolean;
  error: string | null;
  setLeaveToken: (token: string | null) => void;
}

export function useSwipeSessionLifecycle({
  id,
  leaveToken,
  finished,
  error,
  setLeaveToken,
}: UseSwipeSessionLifecycleParams) {
  useEffect(() => {
    if (leaveToken || !id) return;

    let cancelled = false;

    getSwipeSession(id)
      .then((session) => {
        if (!cancelled) {
          setLeaveToken(session.leave_token);
        }
      })
      .catch(() => {
        // Not critical: reaper will end it.
      });

    return () => {
      cancelled = true;
    };
  }, [id, leaveToken, setLeaveToken]);

  useEffect(() => {
    if (!id || finished || error) return;

    const sessionId = id;

    const interval = setInterval(() => {
      void sendHeartbeat(sessionId);
    }, HEARTBEAT_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [id, finished, error]);
}
