import { useState, type ReactNode } from "react";
import { Check, Clock, LogOut } from "lucide-react";

import type { Invite, ParticipantState } from "../services/sessions";
import ConfirmModal from "./modal/ConfirmModal";
import InviteSharePanel from "./InviteSharePanel";
import type { LeaveController } from "../hooks/useLeaveSession";
import LetterboxdImportSection from "./LetterboxdImportSection";
import Waiting from "./Waiting";

type LobbyKind = "comparison" | "swipe";

const COPY = {
  comparison: {
    leaveLabel: "Leave room",
    opening: "Opening the room…",
    invite: { noun: "room", pageName: "Taste comparison" },
    importPurpose: "comparison",
    needsImport:
      "Your friend is in the room. We need your export to compare tastes — the comparison starts as soon as the import finishes.",
    waitingPartnerData:
      "They still need to import their Letterboxd export. The comparison starts automatically once they do.",
  },
  swipe: {
    leaveLabel: "Leave session",
    opening: "Opening the session…",
    invite: { noun: "session", pageName: "Discover together" },
    importPurpose: "recommendations",
    needsImport:
      "Your friend is in the session. We need your export to pick movies for both of you — the session starts as soon as the import finishes.",
    waitingPartnerData:
      "They still need to import their Letterboxd export. The session starts automatically once they do.",
  },
} as const;

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

interface SessionLobbyProps {
  kind: LobbyKind;
  phase: string;
  state: ParticipantState | null;
  initialInvite: Invite | null;
  onRegenerate: () => Promise<Invite>;
  onImported: () => void;
  leave: LeaveController;
  children?: ReactNode;
}

export default function SessionLobby({
  kind,
  phase,
  state,
  initialInvite,
  onRegenerate,
  onImported,
  leave,
  children,
}: SessionLobbyProps) {
  const [isLeaveModalOpen, setIsLeaveModalOpen] = useState(false);

  const copy = COPY[kind];
  const noun = copy.invite.noun;

  const leaveDescription =
    state?.status === "WAITING"
      ? state.partner_joined
        ? `You'll leave the ${noun}. You will no longer be able to join again to this ${noun} again.`
        : `Nobody else is here, so the ${noun} will be deleted.`
      : state?.status === "FINISHED"
        ? `This ${noun} is already closed. You'll go back to the home screen.`
        : `This closes the ${noun} for both of you. You can start a new one at any time.`;

  const showStatus =
    state !== null &&
    phase !== "loading" &&
    phase !== "waiting_partner" &&
    phase !== "ready";

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex w-full max-w-7xl flex-col px-4 py-6 sm:px-6 sm:py-10">
        {state && (state.status !== "FINISHED" || phase === "ready") && (
          <div className="mb-2 flex justify-end">
            <button
              type="button"
              onClick={() => {
                leave.clearLeaveError();
                setIsLeaveModalOpen(true);
              }}
              disabled={leave.isLeaving}
              className="flex cursor-pointer items-center gap-2 border border-border bg-surface px-4 py-2 text-xs font-medium text-text-muted transition hover:bg-surface-hover hover:text-text disabled:cursor-auto disabled:opacity-50"
            >
              <LogOut size={14} strokeWidth={1.7} />
              {copy.leaveLabel}
            </button>
          </div>
        )}

        {phase === "loading" && (
          <Waiting title={copy.opening} text="Just a moment." />
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
              noun={copy.invite.noun}
              pageName={copy.invite.pageName}
            />

            {state && !state.you_have_data && (
              <div>
                <h2 className="text-lg font-semibold">
                  Import your data while you wait
                </h2>

                <div className="mt-3">
                  <LetterboxdImportSection
                    purpose={copy.importPurpose}
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
                {copy.needsImport}
              </p>
            </div>

            <LetterboxdImportSection
              purpose={copy.importPurpose}
              onImported={onImported}
            />
          </div>
        )}

        {phase === "waiting_partner_data" && (
          <Waiting
            title="Waiting for your friend's data"
            text={copy.waitingPartnerData}
          />
        )}

        {children}
      </div>

      {isLeaveModalOpen && (
        <ConfirmModal
          title="Leave session?"
          description={leaveDescription}
          error={leave.leaveError}
          onClose={() => setIsLeaveModalOpen(false)}
          isProcessing={leave.isLeaving}
          actions={[
            {
              label: "Stay",
              onClick: () => setIsLeaveModalOpen(false),
              variant: "secondary",
            },
            {
              label: "Leave",
              loadingLabel: "Leaving...",
              onClick: () => void leave.handleLeave(),
              loading: leave.isLeaving,
            },
          ]}
        />
      )}
    </main>
  );
}