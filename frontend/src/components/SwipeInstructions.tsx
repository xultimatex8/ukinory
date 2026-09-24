import { Check, Heart, X } from "lucide-react";

export default function SwipeInstructions() {
  return (
    <aside className="w-full shrink-0 xl:w-56">
      <div className="border border-border bg-surface p-4 sm:p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          How it works
        </p>

        <div className="mt-4 flex gap-10 lg:gap-5 xl:flex-col">
          <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center border border-red-400/30 bg-red-400/5 text-red-400 sm:h-9 sm:w-9">
              <X size={16} strokeWidth={1.8} />
            </div>

            <p className="text-xs leading-tight text-text-secondary sm:text-sm">
              <span className="block lg:inline">Swipe</span>
              <span className="block lg:ml-1 lg:inline">left</span>
            </p>
          </div>

          <div className="-ml-4 lg:ml-0 flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center border border-emerald-500/40 bg-emerald-500/5 text-emerald-500 sm:h-9 sm:w-9">
              <Check size={16} strokeWidth={1.8} />
            </div>

            <p className="text-xs leading-tight text-text-secondary sm:text-sm">
              Mark as watched
            </p>
          </div>

          <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center border border-primary/40 bg-primary/5 text-primary sm:h-9 sm:w-9">
              <Heart size={16} strokeWidth={1.8} />
            </div>

            <p className="text-xs leading-tight text-text-secondary sm:text-sm">
              <span className="block lg:inline">Swipe</span>
              <span className="block lg:ml-1 lg:inline">right</span>
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}