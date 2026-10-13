import { useCallback, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import ErrorScreen from "../../../../components/ErrorScreen";
import PairedLobby from "../../../../components/PairedLobby";
import { usePairedSession } from "../../../../hooks/usePairedSession";
import {
  endSwipeSession,
  regeneratePairedInvite,
  type PairedInvite,
} from "../../../../services/swipeSessions";
import DiscoverSessionScreen from "../../individual/session";

export default function PairedSessionScreen() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const paired = usePairedSession(id);

  const initialInvite =
    (location.state as { invite?: PairedInvite } | null)?.invite ?? null;
  const [isLeaving, setIsLeaving] = useState(false);
  const [leaveError, setLeaveError] = useState<string | null>(null);

  const handleLeave = useCallback(async () => {
    if (!id) return;

    setIsLeaving(true);
    setLeaveError(null);

    try {
      await endSwipeSession(id);
      navigate("/");
    } catch {
      setIsLeaving(false);
      setLeaveError("Unable to leave the session. Please try again.");
    }
  }, [id, navigate]);

  if (paired.fatal === "not_found") {
    return (
      <ErrorScreen
        message="This swipe session does not exist or is no longer available."
        buttonText="Back to home"
      />
    );
  }

  if (paired.fatal === "forbidden") {
    return (
      <ErrorScreen
        message="You are not a member of this session."
        buttonText="Back to home"
      />
    );
  }

  if (paired.phase === "active" || paired.hasBeenActive) {
    return <DiscoverSessionScreen paired={paired} />;
  }

  if (paired.phase === "closed") {
    return (
      <ErrorScreen
        message="This session was closed before it started."
        buttonText="Back to home"
      />
    );
  }

  return (
    <PairedLobby
      phase={paired.phase}
      state={paired.state}
      initialInvite={initialInvite}
      isLeaving={isLeaving}
      error={paired.error}
      leaveError={leaveError}
      startError={paired.startError}
      onRegenerate={() => regeneratePairedInvite(id!)}
      onImported={() => void paired.refresh()}
      onRetryStart={paired.retryStart}
      onLeave={() => void handleLeave()}
      onClearLeaveError={() => setLeaveError(null)}
    />
  );
}