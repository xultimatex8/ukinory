import { useState } from "react";
import { Heart, Loader2, Star, X } from "lucide-react";
import { rateMovie } from "../services/library";
import { ApiError } from "../services/api";

interface RateMovieModalProps {
  movieId: number;
  movieTitle: string;
  onClose: () => void;
  onSaved: () => void;
}

const STAR_VALUES = [1, 2, 3, 4, 5];
const STAR_SIZE = 32;

function formatStarsLabel(value: number): string {
  return `${value} star${value === 1 ? "" : "s"}`;
}

interface StarInputProps {
  value: number;
  fillLevel: number;
  disabled: boolean;
  onPick: (value: number) => void;
  onHover: (value: number | null) => void;
}

function StarInput({ value, fillLevel, disabled, onPick, onHover }: StarInputProps) {
  const fillPercent = fillLevel * 100;

  return (
    <div
      className="relative"
      style={{ width: STAR_SIZE, height: STAR_SIZE }}
      onMouseLeave={() => onHover(null)}
    >
      <Star size={STAR_SIZE} strokeWidth={1.8} className="pointer-events-none text-primary" />

      <div
        className="pointer-events-none absolute inset-0 overflow-hidden text-primary"
        style={{ width: `${fillPercent}%` }}
      >
        <Star size={STAR_SIZE} strokeWidth={1.8} fill="currentColor" />
      </div>

      <button
        type="button"
        disabled={disabled}
        onClick={() => onPick(value - 0.5)}
        onMouseEnter={() => onHover(value - 0.5)}
        aria-label={formatStarsLabel(value - 0.5)}
        className="absolute inset-y-0 left-0 w-1/2 cursor-pointer disabled:cursor-auto"
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => onPick(value)}
        onMouseEnter={() => onHover(value)}
        aria-label={formatStarsLabel(value)}
        className="absolute inset-y-0 right-0 w-1/2 cursor-pointer disabled:cursor-auto"
      />
    </div>
  );
}

export default function RateMovieModal({
  movieId,
  movieTitle,
  onClose,
  onSaved,
}: RateMovieModalProps) {
  const [rating, setRating] = useState<number | null>(null);
  const [hoveredValue, setHoveredValue] = useState<number | null>(null);
  const [liked, setLiked] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const displayValue = hoveredValue ?? rating ?? 0;

  const handlePick = (value: number) => {
    setRating(rating === value ? null : value);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);

    try {
      await rateMovie(movieId, {
        rating,
        liked,
        watched_date: new Date().toISOString().slice(0, 10),
      });

      onSaved();
    } catch (error) {
      if (error instanceof ApiError) {
        setError(error.detail);
      } else {
        setError("Couldn't save this. Try again.");
      }

      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-sm border border-border bg-surface p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-text">Mark as watched</h2>

            <div className="mt-2 border-l-2 border-primary pl-3">
              <p className="truncate text-sm font-medium text-text">
                {movieTitle}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            aria-label="Close"
            className="shrink-0 cursor-pointer text-text-muted transition hover:text-text disabled:cursor-auto disabled:opacity-40"
          >
            <X size={18} strokeWidth={1.8} />
          </button>
        </div>

        <div className="mt-5 text-center">
          <p className="text-xs text-text-muted">
            Please consider rating it to improve your future recommendations.
          </p>

          <div className="mt-3 flex items-center justify-center gap-1">
            {STAR_VALUES.map((value) => {
              const fillLevel = Math.min(1, Math.max(0, displayValue - (value - 1)));

              return (
                <StarInput
                  key={value}
                  value={value}
                  fillLevel={fillLevel}
                  disabled={isSaving}
                  onPick={handlePick}
                  onHover={setHoveredValue}
                />
              );
            })}
          </div>
        </div>

        <div className="mt-5 flex items-center justify-center">
          <button
            type="button"
            disabled={isSaving}
            onClick={() => setLiked((prev) => !prev)}
            className={`flex cursor-pointer items-center gap-2 border px-4 py-2 text-sm font-medium transition disabled:cursor-auto disabled:opacity-40 ${
              liked
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-text-muted hover:border-text-muted hover:text-text"
            }`}
          >
            <Heart
              size={16}
              strokeWidth={1.8}
              fill={liked ? "currentColor" : "none"}
            />
            {liked ? "Liked" : "Like this"}
          </button>
        </div>

        {error && (
          <p className="mt-4 text-center text-sm text-red-400">{error}</p>
        )}

        <div className="mt-6 flex items-center justify-center gap-3 border-t border-border pt-5">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="cursor-pointer border border-border bg-surface px-4 py-2 text-sm font-medium text-text-muted transition hover:bg-surface-hover hover:text-text disabled:cursor-auto disabled:opacity-40"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={isSaving}
            className="flex cursor-pointer items-center gap-2 border border-primary bg-primary/5 px-4 py-2 text-sm font-medium text-primary transition hover:bg-primary hover:text-background disabled:cursor-auto disabled:opacity-40"
          >
            {isSaving && <Loader2 size={15} className="animate-spin" />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}