import { useState } from "react";
import { Check, Clock, Loader2, LogOut } from "lucide-react";

import type { PairedPhase } from "../hooks/usePairedSession";
import type { PairedInvite, PairedSessionState } from "../services/swipeSessions";
import InviteSharePanel from "./InviteSharePanel";
import ConfirmModal from "./ConfirmModal";
import LetterboxdImportSection from "./LetterboxdImportSesction";

interface PairedLobbyProps {
  phase: PairedPhase;
  state: PairedSessionState | null;
  initialInvite: PairedInvite | null;
  isLeaving: boolean;
  error: string | null;
  leaveError: string | null;
  startError: string | null;
  onRegenerate: () => Promise<PairedInvite>;
  onImported: () => void;
  onRetryStart: () => void;
  onLeave: () => void;
  onClearLeaveError: () => void;
}

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

export default function PairedLobby({
  phase,
  state,
  initialInvite,
  isLeaving,
  error,
  leaveError,
  startError,
  onRegenerate,
  onImported,
  onRetryStart,
  onLeave,
  onClearLeaveError,
}: PairedLobbyProps) {
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);

  const showStatus =
    state !== null && phase !== "loading" && phase !== "waiting_partner";

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex w-full max-w-7xl flex-col px-4 py-6 sm:px-6 sm:py-10">
        {state && state.status !== "FINISHED" && (
          <div className="mb-2 flex justify-end">
            <button
              type="button"
              onClick={() => {
                onClearLeaveError();
                setIsConfirmModalOpen(true);
              }}
              disabled={isLeaving}
              className="flex cursor-pointer items-center gap-2 border border-border bg-surface px-4 py-2 text-xs font-medium text-text-muted transition hover:bg-surface-hover hover:text-text disabled:cursor-auto disabled:opacity-50"
            >
              <LogOut size={14} strokeWidth={1.7} />
              Leave session
            </button>
          </div>
        )}

        {phase === "loading" && (
          <Waiting title="Opening the session…" text="Just a moment." />
        )}

        {phase === "waiting_partner" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-bold">Waiting for your friend</h1>

              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                Send them the link or the code. This page updates by itself as
                soon as they join.
              </p>
            </div>

            <InviteSharePanel
              initialInvite={initialInvite}
              onRegenerate={onRegenerate}
              noun="session"
              pageName="Discover together"
            />

            {state && !state.you_have_data && (
              <div>
                <h2 className="text-lg font-semibold">
                  Import your data while you wait
                </h2>

                <div className="mt-3">
                  <LetterboxdImportSection
                    purpose="recommendations"
                    onImported={onImported}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {showStatus && state && (
          <ul className="mb-6 divide-y divide-border border border-border bg-surface">
            <StatusRow label="You" joined hasData={state.you_have_data} />

            <StatusRow
              label="Your friend"
              joined={state.partner_joined}
              hasData={state.partner_has_data}
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
                Your friend is in the session. We need your export to pick
                movies for both of you — the session starts as soon as the
                import finishes. Else, individually swipe and rate some
                movies.
              </p>
            </div>

            <LetterboxdImportSection
                    purpose="recommendations"
                    onImported={onImported}
                  />
          </div>
        )}

        {phase === "waiting_partner_data" && (
          <Waiting
            title="Waiting for your friend's data"
            text="They still need to import their Letterboxd export. The session starts automatically once they do."
          />
        )}

        {phase === "starting" && (
          <Waiting
            title="Picking movies for both of you…"
            text="This usually takes a few seconds."
          />
        )}

        {phase === "failed" && (
          <div className="border border-border bg-surface px-6 py-10 text-center">
            <h2 className="text-lg font-semibold">
              Something went wrong starting the session
            </h2>

            <p className="mt-2 text-sm text-text-muted">
              {startError ?? "Your data is safe. Try again in a moment."}
            </p>

            <button
              type="button"
              onClick={onRetryStart}
              className="mt-5 inline-flex cursor-pointer items-center gap-2 border border-primary px-5 py-2.5 text-sm font-medium text-primary transition hover:bg-primary hover:text-background"
            >
              Try again
            </button>
          </div>
        )}

        {error && (
          <div className="mt-5 border border-border bg-surface p-4 text-sm text-red-400">
            {error}
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