import { motion } from "motion/react";
import { X } from "lucide-react";

interface EndSessionModalProps {
  isEndingSession: boolean;
  error: string | null;
  onClose: () => void;
  onGoHome: () => void;
  onDownloadCsv: () => void;
}

export default function EndSessionModal({
  isEndingSession,
  error,
  onClose,
  onGoHome,
  onDownloadCsv,
}: EndSessionModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-5 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.2 }}
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-text">
              End session?
            </h2>

            <p className="mt-2 text-sm leading-relaxed text-text-muted">
              You can return home or end the session and
              download your watchlist as a CSV file.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isEndingSession}
            aria-label="Close"
            className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-border
              text-text-muted transition hover:border-primary hover:text-primary disabled:cursor-auto disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="mt-5 rounded-lg border border-red-400/30 bg-red-400/5 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="mt-7 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onGoHome}
            disabled={isEndingSession}
            className="flex-1 cursor-pointer rounded-lg border border-border px-4 py-3 text-sm font-medium text-text transition hover:bg-surface-hover disabled:cursor-auto disabled:opacity-50"
          >
            Back to home
          </button>

          <button
            type="button"
            onClick={onDownloadCsv}
            disabled={isEndingSession}
            className="flex-1 cursor-pointer rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-background transition hover:bg-primary-hover disabled:cursor-auto disabled:opacity-50"
          >
            {isEndingSession
              ? "Ending session..."
              : "Download CSV"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}