import { motion } from "motion/react";
import { X } from "lucide-react";
import type { ReactNode } from "react";

interface ConfirmModalAction {
  label: string;
  loadingLabel?: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: "primary" | "danger" | "secondary";
}

interface ConfirmModalProps {
  title: string;
  description: ReactNode;
  error: string | null;
  onClose: () => void;
  isProcessing?: boolean;
  actions: ConfirmModalAction[];
  rounded?: boolean;
}

export default function ConfirmModal({
  title,
  description,
  error,
  onClose,
  isProcessing = false,
  actions,
  rounded = true,
}: ConfirmModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-5 backdrop-blur-sm"
      onClick={isProcessing ? undefined : onClose}
    >
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.2 }}
        onClick={(event) => event.stopPropagation()}
        className={`w-full max-w-md border border-border bg-surface p-6 shadow-2xl ${
          rounded ? "rounded-xl" : ""
        }`}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-text">{title}</h2>

            <div className="mt-2 text-sm leading-relaxed text-text-muted">
              {description}
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            aria-label="Close"
            className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-border text-text-muted transition hover:border-primary hover:text-primary disabled:cursor-auto disabled:opacity-50"
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
          {actions.map((action) => {
            const variant = action.variant ?? "primary";
            const isDisabled =
              isProcessing || action.disabled || action.loading;

            const buttonStyle = {
              primary:
                "bg-primary text-background hover:bg-primary-hover",
              danger: "bg-red-500 text-white hover:bg-red-400",
              secondary:
                "border border-border text-text hover:bg-surface-hover",
            }[variant];

            return (
              <button
                key={action.label}
                type="button"
                onClick={action.onClick}
                disabled={isDisabled}
                className={`flex-1 cursor-pointer rounded-lg px-4 py-3 text-sm font-semibold transition disabled:cursor-auto disabled:opacity-50 ${buttonStyle}`}
              >
                {action.loading
                  ? action.loadingLabel ?? action.label
                  : action.label}
              </button>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}