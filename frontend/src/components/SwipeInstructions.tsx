import { Heart, X } from "lucide-react";

export default function SwipeInstructions() {
  return (
    <aside className="w-full shrink-0 xl:w-56">
      <div className="border border-border bg-surface p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          How it works
        </p>

        <div className="mt-5 flex gap-6 xl:flex-col xl:gap-4">
          <div className="flex flex-1 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center border border-red-400/30 bg-red-400/5 text-red-400">
              <X size={17} strokeWidth={1.8} />
            </div>

            <p className="text-sm text-text-secondary">
              Swipe left to skip
            </p>
          </div>

          <div className="flex flex-1 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center border border-primary/40 bg-primary/5 text-primary">
              <Heart size={17} strokeWidth={1.8} />
            </div>

            <p className="text-sm text-text-secondary">
              Swipe right to add
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}