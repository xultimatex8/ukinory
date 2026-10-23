import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Heart, Users } from "lucide-react";

import type { PairedSessionController } from "../hooks/usePairedSession";
import MatchesModal from "./modal/MatchesModal";

interface PairedSessionOverlayProps {
  sessionId: string;
  paired: PairedSessionController;
}

const TOAST_MS = 6000;
const ACTIVITY_MS = 4000;

export default function PairedSessionOverlay({
  sessionId,
  paired,
}: PairedSessionOverlayProps) {
  const [showMatches, setShowMatches] = useState(false);
  const { toast, dismissToast, activity, dismissActivity, matchCount } = paired;

  useEffect(() => {
    if (!toast) return;

    const timer = window.setTimeout(dismissToast, TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [toast, dismissToast]);

  useEffect(() => {
    if (!activity) return;

    const timer = window.setTimeout(dismissActivity, ACTIVITY_MS);
    return () => window.clearTimeout(timer);
  }, [activity, dismissActivity]);

  return (
    <>
      <div className="pointer-events-none fixed inset-x-0 top-4 z-40 flex flex-col items-center gap-2 px-4">
        {toast && (
          <motion.div
            key={toast.candidateId}
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            role="status"
            className="pointer-events-auto flex w-full max-w-sm items-start gap-3 border border-primary bg-surface p-4 shadow-2xl"
          >
            <Heart
              size={20}
              strokeWidth={1.8}
              fill="currentColor"
              className="mt-0.5 shrink-0 text-primary"
            />

            <div className="min-w-0">
              <p className="text-sm font-semibold text-text">It's a match</p>
              <p className="mt-1 text-sm leading-snug text-text-muted">
                You both want to watch{" "}
                <span className="text-text">{toast.title}</span>
                {toast.releaseYear ? ` (${toast.releaseYear})` : ""}. It's on
                both watchlists.
              </p>
            </div>
          </motion.div>
        )}

        {activity && !toast && (
          <motion.p
            key={activity.key}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            role="status"
            className="max-w-sm truncate border border-border bg-surface px-3 py-1.5 text-xs text-text-muted"
          >
            {activity.action === "WATCHLIST"
              ? `Your partner added ${activity.title} to their watchlist`
              : `Your partner skipped ${activity.title}`}
          </motion.p>
        )}
      </div>

      <button
        type="button"
        onClick={() => setShowMatches(true)}
        className="fixed right-4 top-4 z-30 flex cursor-pointer items-center gap-2 border border-border bg-surface px-3 py-2 text-xs font-medium text-text-muted transition hover:border-primary hover:text-primary"
      >
        <Users size={14} strokeWidth={1.8} />
        Matches
        <span className="min-w-5 border border-border bg-background px-1.5 text-center text-text">
          {matchCount}
        </span>
      </button>

      {showMatches && (
        <MatchesModal
          sessionId={sessionId}
          onClose={() => setShowMatches(false)}
        />
      )}
    </>
  );
}