import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Users } from "lucide-react";

import type { PairedSessionController } from "../hooks/usePairedSession";
import MatchesModal from "./modal/MatchesModal";
import MatchCelebration from "./MatchCelebration";

interface PairedSessionOverlayProps {
  sessionId: string;
  paired: PairedSessionController;
}

const ACTIVITY_MS = 4000;

export default function PairedSessionOverlay({
  sessionId,
  paired,
}: PairedSessionOverlayProps) {
  const [showMatches, setShowMatches] = useState(false);
  const { toast, dismissToast, activity, dismissActivity, matchCount } = paired;

  useEffect(() => {
    if (!activity) return;

    const timer = window.setTimeout(dismissActivity, ACTIVITY_MS);
    return () => window.clearTimeout(timer);
  }, [activity, dismissActivity]);

  const handleViewMatches = () => {
    dismissToast();
    setShowMatches(true);
  };

  return (
    <>
      <div className="pointer-events-none fixed inset-x-0 top-4 z-40 flex flex-col items-center gap-2 px-4">
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

  <div className="flex justify-end px-4 py-2">
    <button
      type="button"
      onClick={() => setShowMatches(true)}
      className="fixed bottom-6 right-6 z-50 flex cursor-pointer items-center gap-2 border border-border 
        bg-surface px-4 py-2 text-xs font-medium text-text-muted shadow-lg transition hover:border-primary hover:text-primary"
    >
      <Users size={14} strokeWidth={1.7} />
      Matches
      <span className={`min-w-5 border bg-background px-1.5 text-center ${
        matchCount > 0 ? "border-primary text-primary" : "border-border text-text"
      }`}>
        {matchCount}
      </span>
    </button>
  </div>

      <MatchCelebration
        match={toast}
        onDismiss={dismissToast}
        onViewMatches={handleViewMatches}
      />

      {showMatches && (
        <MatchesModal
          sessionId={sessionId}
          onClose={() => setShowMatches(false)}
        />
      )}
    </>
  );
}