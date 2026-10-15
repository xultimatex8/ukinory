import { useEffect, useState } from "react";
import { Check, Clock, Loader2, LogOut } from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import ErrorScreen from "../../../components/ErrorScreen";
import { getCurrentUser, type User } from "../../../services/user";
import {
  leaveRoom,
  regenerateInvite,
  type Invite,
} from "../../../services/comparisons";
import { useComparisonRoom } from "../../../hooks/useComparisonRoom";
import InviteSharePanel from "../../../components/InviteSharePanel";
import ComparisonResultView from "../../../components/ComparisonResultView";
import ConfirmModal from "../../../components/ConfirmModal";
import LetterboxdImportSection from "../../../components/LetterboxdImportSesction";

function StatusRow({
  label,
  joined,
  hasData,
}: {
  label: string;
  joined: boolean;
  hasData: boolean | null;
}) {
  let text = "Hasn't joined yet";
  let done = false;

  if (joined && hasData) {
    text = "Joined · data imported";
    done = true;
  } else if (joined && hasData === false) {
    text = "Joined · needs to import their data";
  } else if (joined) {
    text = "Joined";
    done = true;
  }

  return (
    <li className="flex items-center justify-between gap-4 px-4 py-3 text-sm">
      <span className="text-text">{label}</span>
      <span
        className={`inline-flex items-center gap-1.5 text-xs ${
          done ? "text-emerald-400" : "text-text-muted"
        }`}
      >
        {done ? <Check size={14} /> : <Clock size={14} />}
        {text}
      </span>
    </li>
  );
}

function Waiting({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex flex-col items-center border border-border bg-surface px-6 py-12 text-center">
      <Loader2 size={26} className="animate-spin text-primary" />
      <h2 className="mt-4 text-lg font-semibold">{title}</h2>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-text-muted">
        {text}
      </p>
    </div>
  );
}

export default function ComparisonRoomScreen() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const initialInvite =
    (location.state as { invite?: Invite } | null)?.invite ?? null;

  const {
    room,
    result,
    phase,
    error,
    fatal,
    isGenerating,
    refresh,
    reload,
    retryGeneration,
  } = useComparisonRoom(id);

  const [me, setMe] = useState<User | null>(null);
  const [meChecked, setMeChecked] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [leaveError, setLeaveError] = useState<string | null>(null);

  const handleLeave = async () => {
    if (!id || isLeaving) return;

    setIsLeaving(true);
    setLeaveError(null);

    try {
      await leaveRoom(id);
      navigate("/");
    } catch {
      setIsLeaving(false);
      setLeaveError("Unable to leave the room. Please try again.");
    }
  };

  const onLeave = () => {
    if (isLeaving) return;

    void handleLeave();
  };

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
        message="This comparison room is closed."
        buttonText="Back to home"
      />
    );
  }

  if (error) {
    return <ErrorScreen message={error} onRetry={reload} />;
  }

  const showStatus =
    room !== null &&
    phase !== "ready" &&
    phase !== "waiting_partner";

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex w-full max-w-7xl flex-col px-4 py-6 sm:px-6 sm:py-10">
        {room && room.status !== "FINISHED" && (
          <div className="mb-2 flex justify-end">
            <button
              type="button"
              onClick={() => {
                setLeaveError(null);
                setIsConfirmModalOpen(true);
              }}
              disabled={isLeaving}
              className="flex cursor-pointer items-center gap-2 border border-border bg-surface px-4 py-2 text-xs font-medium text-text-muted transition hover:bg-surface-hover hover:text-text disabled:cursor-auto disabled:opacity-50"
            >
              <LogOut size={14} strokeWidth={1.7} />
              Leave room
            </button>
          </div>
        )}

        {phase === "loading" && (
          <Waiting
            title="Opening the room…"
            text="Just a moment."
          />
        )}

        {phase === "waiting_partner" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-bold">
                Waiting for your friend
              </h1>

              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                Send them the link or the code. This page updates by
                itself as soon as they join.
              </p>
            </div>

            <InviteSharePanel
              initialInvite={initialInvite}
              onRegenerate={() => regenerateInvite(id!)}
            />

            {room && !room.you_have_data && (
              <div>
                <h2 className="text-lg font-semibold">
                  Import your data while you wait
                </h2>

                <div className="mt-3">
                  <LetterboxdImportSection
                    purpose="comparison"
                    onImported={() => void refresh()}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {showStatus && room && (
          <ul className="mb-6 divide-y divide-border border border-border bg-surface">
            <StatusRow
              label="You"
              joined
              hasData={room.you_have_data}
            />

            <StatusRow
              label="Your friend"
              joined={room.partner_joined}
              hasData={room.partner_has_data}
            />
          </ul>
        )}

        {phase === "needs_import" && (
          <div className="space-y-4">
            <div>
              <h1 className="text-2xl font-bold">
                Import your Letterboxd data
              </h1>

              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                Your friend is in the room. We need your export to pick
                movies for both of you — the session starts as soon as the
                import finishes. Else, individually swipe and rate some
                movies.
              </p>
            </div>

            <LetterboxdImportSection

              purpose="comparison"

              onImported={() => void refresh()}

            />
          </div>
        )}

        {phase === "waiting_partner_data" && (
          <Waiting
            title="Waiting for your friend's data"
            text="They still need to import their Letterboxd export. The comparison starts automatically once they do."
          />
        )}

        {phase === "generating" && (
          <Waiting
            title="Comparing your tastes…"
            text="This usually takes a few seconds."
          />
        )}

        {phase === "failed" && (
          <div className="border border-border bg-surface px-6 py-10 text-center">
            <h2 className="text-lg font-semibold">
              Something went wrong comparing your tastes
            </h2>

            <p className="mt-2 text-sm text-text-muted">
              Your data is safe. Try again in a moment.
            </p>

            <button
              type="button"
              disabled={isGenerating}
              onClick={retryGeneration}
              className="mt-5 inline-flex cursor-pointer items-center gap-2 border border-primary px-5 py-2.5 text-sm font-medium text-primary transition hover:bg-primary hover:text-background disabled:cursor-auto disabled:opacity-40"
            >
              {isGenerating && (
                <Loader2
                  size={15}
                  className="animate-spin"
                />
              )}

              Try again
            </button>
          </div>
        )}

        {phase === "ready" && result && !meChecked && (
          <Waiting
            title="Almost there…"
            text="Loading your results."
          />
        )}

        {phase === "ready" && result && meChecked && (
          <div>
            <h1 className="mb-6 text-2xl font-bold">
              Your taste comparison
            </h1>

            <ComparisonResultView
              result={result}
              currentUserId={me?.id ?? null}
              roomId={id!}
            />
          </div>
        )}
      </div>

      {isConfirmModalOpen && (
        <ConfirmModal
          title="Leave session?"
          description="This closes the session for both of you. You can start a new one at any time."
          error={leaveError}
          onClose={() => setIsConfirmModalOpen(false)}
          isProcessing={isLeaving}
          actions={[
            {
              label: "Stay",
              onClick: () => setIsConfirmModalOpen(false),
              variant: "secondary",
            },
            {
              label: "Leave",
              loadingLabel: "Leaving...",
              onClick: onLeave,
              loading: isLeaving,
            },
          ]}
        />
      )}
    </main>
  );
}