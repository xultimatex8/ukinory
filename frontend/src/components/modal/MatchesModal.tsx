import { useEffect, useState } from "react";
import { ExternalLink, Heart, Loader2, X } from "lucide-react";
import {
  type SessionMatch,
  getSessionMatches,
} from "../../services/swipeSessions";
import { getErrorMessage } from "../../utils/errors";
import { letterboxdUrl } from "../../utils/movie";

interface MatchesModalProps {
  sessionId: string;
  onClose: () => void;
}

function formatMatchTime(value: string | null): string | null {
  if (!value) return null;

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function MatchesModal({
  sessionId,
  onClose,
}: MatchesModalProps) {
  const [matches, setMatches] = useState<SessionMatch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    let cancelled = false;

    getSessionMatches(sessionId)
      .then((data) => {
        if (!cancelled) setMatches(data);
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err));
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const count = matches?.length ?? 0;

  const subtitle =
    matches === null
      ? "Movies you both added to your watchlist"
      : count === 0
        ? "Your shared movie list starts here"
        : count === 1
          ? "1 movie you both want to watch"
          : `${count} movies you both want to watch`;

  const handleRetry = async () => {
    setRetrying(true);
    setError(null);
    setMatches(null);

    try {
      const data = await getSessionMatches(sessionId);
      setMatches(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Your matches"
      className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-background"
    >
      <header className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4 sm:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-primary/30 bg-primary/10 text-primary">
            <Heart size={19} fill="currentColor" />
          </div>

          <div className="min-w-0">
            <h2 className="text-base font-bold text-text">
              Your matches
            </h2>
            <p className="text-xs text-text-muted">{subtitle}</p>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          aria-label="Close matches"
          className="ml-4 shrink-0 cursor-pointer border border-border bg-surface p-2 text-text-secondary transition-colors hover:border-primary hover:text-primary"
        >
          <X size={18} />
        </button>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full w-full max-w-[1600px] flex-col px-5 py-6 sm:px-8 sm:py-8 lg:px-10">
          {error && (
            <div
              role="alert"
              className="mx-auto w-full max-w-lg border border-border bg-surface p-5 text-center"
            >
              <p className="text-sm font-semibold text-text">
                Couldn't load your matches
              </p>

              <p className="mt-2 text-sm text-text-muted">{error}</p>

              <button
                type="button"
                onClick={handleRetry}
                disabled={retrying}
                className="mt-4 cursor-pointer border border-border px-4 py-2 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:cursor-wait disabled:opacity-50"
              >
                {retrying ? "Loading..." : "Try again"}
              </button>
            </div>
          )}

          {!error && matches === null && (
            <div className="flex flex-1 items-center justify-center py-20">
              <Loader2
                size={26}
                className="animate-spin text-primary"
                aria-label="Loading matches"
              />
            </div>
          )}

          {!error && matches !== null && count === 0 && (
            <div className="flex flex-1 flex-col items-center justify-center py-12 text-center">
              <div className="relative mb-6 flex h-24 w-24 items-center justify-center border border-border bg-surface">
                <Heart
                  size={36}
                  strokeWidth={1.2}
                  className="text-primary"
                />
                <span className="absolute -right-1 -top-1 h-4 w-4 border-2 border-background bg-primary" />
              </div>

              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
                Your movie night
              </p>

              <h3 className="mt-3 text-2xl font-bold tracking-tight text-text sm:text-3xl">
                Nothing in common. Yet.
              </h3>

              <p className="mt-3 max-w-sm text-sm leading-6 text-text-muted">
                Keep swiping together. When you both add the same movie to
                your watchlists, it'll show up here.
              </p>

              <button
                type="button"
                onClick={onClose}
                className="mt-7 cursor-pointer border border-primary bg-primary px-6 py-3 text-xs font-bold text-background transition-opacity hover:opacity-80"
              >
                Keep swiping
              </button>
            </div>
          )}

          {!error && matches !== null && count > 0 && (
            <>
              <div className="mb-7 flex items-center gap-3 border-b border-border pb-5">
                <div className="h-8 w-1 shrink-0 bg-primary" />

                <div>
                  <h3 className="text-lg font-bold text-text">
                    {count === 1 ? "It's a match!" : "Your picks"}
                  </h3>

                  <p className="mt-0.5 text-xs text-text-muted">
                    {count === 1
                      ? "One movie you can both agree on."
                      : `${count} movies for your next movie night.`}
                  </p>
                </div>
              </div>

              <ul className="grid grid-cols-2 items-start gap-x-4 gap-y-6 sm:grid-cols-3 sm:gap-x-5 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
                {matches.map((match, index) => {
                  const time = formatMatchTime(match.matched_at);

                  return (
                    <li
                      key={match.candidate_id}
                      className="group flex min-w-0 flex-col overflow-hidden border border-border bg-surface p-3 transition-colors hover:border-primary/60"
                    >
                      {match.movie.poster_url ? (
                        <img
                          src={match.movie.poster_url}
                          alt={`${match.movie.title} poster`}
                          loading="lazy"
                          className="aspect-2/3 w-full border-b border-border object-cover object-center"
                        />
                      ) : (
                        <div className="flex aspect-2/3 w-full items-center justify-center border-b border-border bg-background text-text-muted">
                          <Heart size={24} strokeWidth={1.2} />
                        </div>
                      )}

                      <div className="flex min-w-0 flex-1 flex-col pt-3">
                        <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-wider">
                          <span className="flex items-center gap-1 text-primary">
                            <Heart size={11} fill="currentColor" />
                            Match
                          </span>

                          {index === 0 && count > 1 && (
                            <span className="border border-primary px-1.5 py-0.5 text-primary">
                              Latest
                            </span>
                          )}
                        </div>

                        <h3 className="mt-2 line-clamp-2 min-h-10 text-sm font-bold leading-snug text-text">
                          {match.movie.title}
                        </h3>

                        {match.movie.release_year && (
                          <p className="mt-1 text-xs text-text-muted">
                            {match.movie.release_year}
                          </p>
                        )}

                        {time && (
                          <p className="mt-2 text-xs text-text-muted">
                            Matched at {time}
                          </p>
                        )}

                        <a
                          href={letterboxdUrl(match.movie.tmdb_id)}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`Open ${match.movie.title} on Letterboxd`}
                          className="mt-3 flex items-center justify-center gap-2 border border-border bg-background px-2 py-2 text-xs font-semibold text-text-secondary transition-colors hover:border-primary hover:text-primary"
                        >
                          Letterboxd
                          <ExternalLink size={12} />
                        </a>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      </main>
    </div>
  );
}