import { useLocation, useParams } from "react-router-dom";

import ErrorScreen from "../../../../components/ErrorScreen";
import FailurePanel from "../../../../components/FailurePanel";
import SessionLobby from "../../../../components/SessionLobby";
import Waiting from "../../../../components/Waiting";
import { useLeaveSession } from "../../../../hooks/useLeaveSession";
import { usePairedSession } from "../../../../hooks/usePairedSession";
import {
  leaveSwipeSession,
  regeneratePairedInvite,
  type PairedInvite,
} from "../../../../services/swipeSessions";
import DiscoverSessionScreen from "../../individual/session";

export default function PairedSessionScreen() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();

  const paired = usePairedSession(id);
  const leave = useLeaveSession(id, leaveSwipeSession, "session");

  // While leaving, our own refresh may fail (403 / closed): don't flash it.
  const fatal = leave.isLeaving ? null : paired.fatal;

  const initialInvite =
    (location.state as { invite?: PairedInvite } | null)?.invite ?? null;

  if (fatal === "not_found") {
    return (
      <ErrorScreen
        message="This swipe session does not exist or is no longer available."
        buttonText="Back to home"
      />
    );
  }

  if (fatal === "forbidden") {
    return (
      <ErrorScreen
        message="You are not a member of this session."
        buttonText="Back to home"
      />
    );
  }

  if (fatal === "closed") {
    return (
      <ErrorScreen
        message="This session is no longer available."
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
    <SessionLobby
      kind="swipe"
      phase={paired.phase}
      state={paired.state}
      initialInvite={initialInvite}
      onRegenerate={() => regeneratePairedInvite(id!)}
      onImported={() => void paired.refresh()}
      leave={leave}
    >
      {paired.phase === "starting" && (
        <Waiting
          title="Picking movies for both of you…"
          text="This usually takes a few seconds."
        />
      )}

      {paired.phase === "failed" && (
        <FailurePanel
          title="Something went wrong starting the session"
          text={paired.startError ?? "Your data is safe. Try again in a moment."}
          onRetry={paired.retryStart}
        />
      )}

      {paired.error && (
        <div className="mt-5 border border-border bg-surface p-4 text-sm text-red-400">
          {paired.error}
        </div>
      )}
    </SessionLobby>
  );
}