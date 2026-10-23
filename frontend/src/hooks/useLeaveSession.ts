
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

export function useLeaveSession(
  sessionId: string | undefined,
  leave: (sessionId: string) => Promise<unknown>,
  noun: "room" | "session",
) {
  const navigate = useNavigate();

  const [isLeaving, setIsLeaving] = useState(false);
  const [leaveError, setLeaveError] = useState<string | null>(null);

  const handleLeave = useCallback(async () => {
    if (!sessionId || isLeaving) return;

    setIsLeaving(true);
    setLeaveError(null);

    try {
      await leave(sessionId);
      void navigate("/");
    } catch {
      setLeaveError(`Unable to leave the ${noun}. Please try again.`);
    } finally {
      setIsLeaving(false);
    }
  }, [sessionId, isLeaving, leave, noun, navigate]);

  const clearLeaveError = useCallback(() => {
    setLeaveError(null);
  }, []);

  return {
    isLeaving,
    leaveError,
    handleLeave,
    clearLeaveError,
  };
}

export type LeaveController = ReturnType<typeof useLeaveSession>;