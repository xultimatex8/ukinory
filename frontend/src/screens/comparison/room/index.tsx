import { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";

import ComparisonResultView from "../../../components/ComparisonResultView";
import ErrorScreen from "../../../components/ErrorScreen";
import FailurePanel from "../../../components/FailurePanel";
import SessionLobby from "../../../components/SessionLobby";
import Waiting from "../../../components/Waiting";
import { useComparisonRoom } from "../../../hooks/useComparisonRoom";
import { useLeaveSession } from "../../../hooks/useLeaveSession";
import {
  leaveRoom,
  regenerateInvite,
  type Invite,
} from "../../../services/comparisons";
import { getCurrentUser, type User } from "../../../services/user";

export default function ComparisonRoomScreen() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const initialInvite =
    (location.state as { invite?: Invite } | null)?.invite ?? null;

  const {
    room,
    result,
    phase,
    roomClosed,
    error,
    fatal: fatalError,
    isGenerating,
    refresh,
    reload,
    retryGeneration,
  } = useComparisonRoom(id);

  const leave = useLeaveSession(id, leaveRoom, "room");

  // While leaving, our own refresh may fail (403 / closed): don't flash it.
  const fatal = leave.isLeaving ? null : fatalError;

  const [me, setMe] = useState<User | null>(null);
  const [meChecked, setMeChecked] = useState(false);

  useEffect(() => {
    if (!result) return;

    let cancelled = false;

    getCurrentUser()
      .then((user) => {
        if (!cancelled) setMe(user);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setMeChecked(true);
      });

    return () => {
      cancelled = true;
    };
  }, [result]);

  if (fatal === "not_found") {
    return (
      <ErrorScreen
        message="This room doesn't exist or is no longer available."
        buttonText="Back to home"
      />
    );
  }

  if (fatal === "forbidden") {
    return (
      <ErrorScreen
        message="You're not part of this room."
        buttonText="Back to home"
      />
    );
  }

  if (fatal === "closed") {
    return (
      <ErrorScreen
        message="This room is closed. Your friend may have left."
        buttonText="Back to home"
      />
    );
  }

  if (error) {
    return <ErrorScreen message={error} onRetry={reload} />;
  }

  return (
    <SessionLobby
      kind="comparison"
      phase={phase}
      state={room}
      initialInvite={initialInvite}
      onRegenerate={() => regenerateInvite(id!)}
      onImported={() => void refresh()}
      leave={leave}
    >
      {phase === "generating" && (
        <Waiting
          title="Comparing your tastes…"
          text="This usually takes a few seconds."
        />
      )}

      {phase === "failed" && (
        <FailurePanel
          title="Something went wrong comparing your tastes"
          text="Your data is safe. Try again in a moment."
          onRetry={retryGeneration}
          isRetrying={isGenerating}
        />
      )}

      {phase === "ready" && result && !meChecked && (
        <Waiting title="Almost there…" text="Loading your results." />
      )}

      {phase === "ready" && result && meChecked && (
        <div>
          {roomClosed && (
            <div
              role="status"
              className="mb-6 border border-border bg-surface p-4 text-sm text-text-muted"
            >
              This room is closed because your friend left. You can still
              review your results.
            </div>
          )}

          <h1 className="mb-6 text-2xl font-bold">Your taste comparison</h1>

          <ComparisonResultView
            result={result}
            currentUserId={me?.id ?? null}
            roomId={id!}
          />
        </div>
      )}
    </SessionLobby>
  );
}