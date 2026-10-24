import { Check, Heart, X } from "lucide-react";

const BASE =
  "flex h-12 min-w-0 cursor-pointer items-center justify-center gap-1.5 border px-2 text-xs font-medium transition disabled:cursor-auto disabled:opacity-40 sm:w-28 sm:gap-2 sm:px-0 sm:text-sm";

interface SwipeActionBarProps {
  disabled: boolean;
  onSkip: () => void;
  onWatched: () => void;
  onWatchlist: () => void;
}

export default function SwipeActionBar({
  disabled,
  onSkip,
  onWatched,
  onWatchlist,
}: SwipeActionBarProps) {
  const actions = [
    {
      label: "Skip",
      ariaLabel: "Skip",
      Icon: X,
      iconSize: 18,
      onClick: onSkip,
      className:
        "border-red-400/30 bg-red-400/5 text-red-400 hover:border-red-400/60 hover:bg-red-400/10",
    },
    {
      label: "Watched",
      ariaLabel: "Mark as watched",
      Icon: Check,
      iconSize: 16,
      onClick: onWatched,
      className:
        "border-emerald-400/50 bg-emerald-400/5 text-emerald-400 hover:border-emerald-400 hover:bg-emerald-400 hover:text-background",
    },
    {
      label: "Watchlist",
      ariaLabel: "Add to watchlist",
      Icon: Heart,
      iconSize: 18,
      onClick: onWatchlist,
      className:
        "border-primary/50 bg-primary/5 text-primary hover:border-primary hover:bg-primary hover:text-background",
    },
  ];

  return (
    <div className="grid w-full grid-cols-3 gap-2 sm:flex sm:items-center sm:justify-center sm:gap-4">
      {actions.map(({ label, ariaLabel, Icon, iconSize, onClick, className }) => (
        <button
          key={label}
          type="button"
          disabled={disabled}
          onClick={onClick}
          aria-label={ariaLabel}
          className={`${BASE} ${className}`}
        >
          <Icon size={iconSize} strokeWidth={1.8} />
          <span className="truncate">{label}</span>
        </button>
      ))}
    </div>
  );
}