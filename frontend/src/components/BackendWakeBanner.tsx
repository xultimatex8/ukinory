import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Loader2, RefreshCw, ServerOff, X } from "lucide-react";

import {
  useBackendWarmup,
  type BackendStatus,
} from "../hooks/useBackendWarmup";

export default function BackendWakeBanner() {
  const status = useBackendWarmup();
  const [dismissedStatus, setDismissedStatus] =
    useState<BackendStatus | null>(null);

  const isError = status === "unreachable";
  const visible =
    (status === "waking" || status === "unreachable") &&
    dismissedStatus !== status;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key={status}
          role="status"
          aria-live="polite"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 24 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className={`fixed inset-x-0 bottom-10 z-50 mx-auto w-[calc(100%-2rem)] max-w-md
                      overflow-hidden border border-l-2 border-border bg-surface
                      shadow-xl shadow-black/30 ${
                        isError ? "border-l-red-500" : "border-l-primary"
                      }`}
        >
          <div className="flex items-start gap-3 p-4">
            <div className="mt-0.5 shrink-0">
              {isError ? (
                <ServerOff
                  size={20}
                  strokeWidth={1.8}
                  className="text-red-500"
                />
              ) : (
                <Loader2
                  size={20}
                  strokeWidth={1.8}
                  className="animate-spin text-primary"
                />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text">
                {isError ? "Unable to reach the server" : "Starting the server…"}
              </p>

              <p className="mt-1 text-sm leading-relaxed text-text-muted">
                {isError
                  ? "The server isn't responding. Please try again in a few minutes."
                  : "It goes to sleep when inactive and can take up to a minute to wake up. Some features won't work until it's ready."}
              </p>

              {isError && (
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="mt-3 inline-flex items-center gap-2 border border-border px-3 py-1.5
                             text-sm font-medium text-text transition
                             hover:border-primary hover:text-primary cursor-pointer"
                >
                  <RefreshCw size={14} strokeWidth={2} />
                  Reload page
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={() => setDismissedStatus(status)}
              aria-label="Dismiss"
              className="shrink-0 text-text-muted transition hover:text-text cursor-pointer"
            >
              <X size={16} strokeWidth={2} />
            </button>
          </div>

          {!isError && (
            <div className="h-0.5 w-full overflow-hidden bg-border">
              <motion.div
                className="h-full w-1/3 bg-primary"
                animate={{ x: ["-100%", "300%"] }}
                transition={{
                  duration: 1.6,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              />
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}