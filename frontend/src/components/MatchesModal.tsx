import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";

import { getSessionMatches, type SessionMatch } from "../services/swipeSessions";
import { getErrorMessage } from "../utils/errors";

interface MatchesModalProps {
  sessionId: string;
  onClose: () => void;
}

export default function MatchesModal({ sessionId, onClose }: MatchesModalProps) {
  const [matches, setMatches] = useState<SessionMatch[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto border border-border bg-surface"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-sm font-semibold text-text">Your matches</h2>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="cursor-pointer p-1 text-text-muted transition hover:text-text"
          >
            <X size={19} />
          </button>
        </div>

        <div className="p-6">
          {error && <p className="text-sm text-red-400">{error}</p>}

          {!error && matches === null && (
            <div className="flex justify-center py-6">
              <Loader2 size={22} className="animate-spin text-primary" />
            </div>
          )}

          {matches !== null && matches.length === 0 && (
            <p className="text-sm leading-relaxed text-text-muted">
              No matches yet. A movie shows up here when you both add it to
              your watchlist.
            </p>
          )}

          {matches !== null && matches.length > 0 && (
            <ul className="flex flex-col gap-4">
              {matches.map((match) => (
                <li key={match.candidate_id} className="flex items-center gap-4">
                  {match.movie.poster_url ? (
                    <img
                      src={match.movie.poster_url}
                      alt={`${match.movie.title} poster`}
                      className="h-20 w-14 shrink-0 border border-border object-cover"
                    />
                  ) : (
                    <div className="h-20 w-14 shrink-0 border border-border bg-background" />
                  )}

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-text">
                      {match.movie.title}
                    </p>

                    {match.movie.release_year && (
                      <p className="mt-0.5 text-xs text-text-muted">
                        {match.movie.release_year}
                      </p>
                    )}
                  </div>

                  <a
                    href={`https://letterboxd.com/tmdb/${match.movie.tmdb_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 border border-border bg-background px-3 py-2 text-xs font-semibold text-text-secondary transition-colors hover:border-primary hover:text-primary"
                  >
                    Letterboxd
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}