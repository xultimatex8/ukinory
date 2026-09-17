import { Heart, X } from "lucide-react";

export default function SwipeInstructions() {
  return (
    <aside className="hidden w-56 shrink-0 lg:block">
      <div className="border border-border bg-surface p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          How it works
        </p>

        <div className="mt-5 space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center border border-red-400/30 bg-red-400/5 text-red-400">
              <X size={17} strokeWidth={1.8} />
            </div>

            <p className="text-sm text-text-secondary">
              Swipe left to skip
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center border border-primary/40 bg-primary/5 text-primary">
              <Heart size={17} strokeWidth={1.8} />
            </div>

            <p className="text-sm text-text-secondary">
              Swipe right to save
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}