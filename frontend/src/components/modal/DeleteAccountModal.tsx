import { useState } from "react";
import { motion } from "motion/react";
import { Eye, EyeOff, X } from "lucide-react";

interface DeleteAccountModalProps {
  isDeleting: boolean;
  isGuest: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (password?: string) => void;
}

export default function DeleteAccountModal({
  isDeleting,
  isGuest,
  error,
  onClose,
  onConfirm,
}: DeleteAccountModalProps) {
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleConfirm = () => {
    if (isGuest) {
      onConfirm();
      return;
    }

    onConfirm(password);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-5 backdrop-blur-sm"
      onClick={isDeleting ? undefined : onClose}
    >
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.2 }}
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md border border-border bg-surface p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-text">
              Delete account?
            </h2>

            <p className="mt-2 text-sm leading-relaxed text-text-muted">
              This action is permanent. Your account and associated data will
              be deleted and cannot be recovered.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            aria-label="Close"
            className="flex h-9 w-9 shrink-0 cursor-pointer items-center
                       justify-center border border-border text-text-muted
                       transition hover:border-primary hover:text-primary
                       disabled:cursor-auto disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        {!isGuest && (
          <div className="mt-6">
            <label
              htmlFor="delete-account-password"
              className="mb-2 block text-sm font-medium text-text"
            >
              Password
            </label>

            <div className="relative">
              <input
                id="delete-account-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                disabled={isDeleting}
                className="w-full border border-border bg-background px-4 py-3 pr-12
                           text-text outline-none transition
                           placeholder:text-text-muted
                           focus:border-primary
                           disabled:cursor-auto disabled:opacity-50"
                placeholder="Enter your password"
              />

              <button
                type="button"
                onClick={() => setShowPassword((previous) => !previous)}
                disabled={isDeleting}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-3 top-1/2 -translate-y-1/2
                           cursor-pointer p-1 text-text-muted transition
                           hover:text-text disabled:cursor-auto
                           disabled:opacity-50"
              >
                {showPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-5 border border-red-400/30 bg-red-400/5 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="flex-1 cursor-pointer border border-border px-4 py-3
                       text-sm font-medium text-text transition
                       hover:bg-surface-hover
                       disabled:cursor-auto disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleConfirm}
            disabled={isDeleting || (!isGuest && !password)}
            className="flex-1 cursor-pointer bg-red-500 px-4 py-3
                       text-sm font-semibold text-white transition
                       hover:bg-red-400
                       disabled:cursor-auto disabled:opacity-50"
          >
            {isDeleting ? "Deleting account..." : "Delete account"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}