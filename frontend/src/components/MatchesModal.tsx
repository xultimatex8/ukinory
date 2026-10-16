import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { getSessionMatches, type SessionMatch } from "../services/swipeSessions";
import { getErrorMessage } from "../utils/errors";
import { letterboxdUrl } from "../utils/movie";
import Modal from "./Modal";

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
    <Modal
      title="Your matches"
      size="md"
      titleClassName="text-sm font-semibold text-text"
      onClose={onClose}
    >
      {error && <p className="text-sm text-red-400">{error}</p>}

      {!error && matches === null && (
        <div className="flex justify-center py-6">
          <Loader2 size={22} className="animate-spin text-primary" />
        </div>
      )}

      {matches !== null && matches.length === 0 && (
        <p className="text-sm leading-relaxed text-text-muted">
          No matches yet. A movie shows up here when you both add it to your
          watchlist.
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
                href={letterboxdUrl(match.movie.tmdb_id)}
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
    </Modal>
  );
}