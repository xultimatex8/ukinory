import { Star } from "lucide-react";

import type {
  ComparisonEntry,
  ComparisonResult,
} from "../services/comparisons";

interface ComparisonResultViewProps {
  result: ComparisonResult;
  currentUserId: number | string | null;
}

function toPercent(value: number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

function ComparisonMovieCard({
  entry,
  youKey,
  partnerKey,
}: {
  entry: ComparisonEntry;
  youKey: string;
  partnerKey: string;
}) {
  return (
    <article className="border border-border bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-xl font-semibold leading-snug text-text">
            {entry.title}
          </h3>

          {entry.release_year && (
            <p className="mt-1 text-sm text-text-muted">
              {entry.release_year}
            </p>
          )}
        </div>

        <div className="shrink-0 text-right">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Ratings
          </p>

          <div className="mt-1 flex items-center gap-2 text-xs text-text-secondary">
            <span className="inline-flex items-center gap-1">
              <Star size={12} fill="currentColor" />
              You {entry.ratings[youKey] ?? "–"}
            </span>

            <span className="text-border">·</span>

            <span className="inline-flex items-center gap-1">
              <Star size={12} fill="currentColor" />
              Friend {entry.ratings[partnerKey] ?? "–"}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}

function ComparisonMovieGrid({
  entries,
  youKey,
  partnerKey,
  emptyText,
}: {
  entries: ComparisonEntry[];
  youKey: string;
  partnerKey: string;
  emptyText: string;
}) {
  if (entries.length === 0) {
    return <p className="mt-3 text-sm text-text-muted">{emptyText}</p>;
  }

  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-2">
      {entries.map((entry) => (
        <ComparisonMovieCard
          key={`${entry.title}-${entry.release_year}`}
          entry={entry}
          youKey={youKey}
          partnerKey={partnerKey}
        />
      ))}
    </div>
  );
}

export default function ComparisonResultView({
  result,
  currentUserId,
}: ComparisonResultViewProps) {
  const { metrics, recommendations } = result;

  const keys = Object.keys(metrics.library_sizes);
  const youKey =
    keys.find((key) => key === String(currentUserId)) ?? keys[0] ?? "";
  const partnerKey = keys.find((key) => key !== youKey) ?? "";

  const score = metrics.compatibility_score;
  const similarity = toPercent(metrics.taste_similarity);

  return (
    <div className="space-y-10">
      <section className="border border-border bg-surface p-6">
        <p className="text-sm text-text-muted">Taste compatibility</p>

        {score !== null ? (
          <>
            <p className="mt-2 text-5xl font-semibold text-primary">
              {score}%
            </p>

            <div className="mt-4 h-1.5 w-full bg-background">
              <div
                className="h-full bg-primary"
                style={{
                  width: `${Math.max(0, Math.min(100, score))}%`,
                }}
              />
            </div>
          </>
        ) : (
          <p className="mt-2 text-sm text-text-secondary">
            There isn't enough shared data to calculate a score yet.
          </p>
        )}

        {result.narrative_available && result.narrative ? (
          <p className="mt-6 text-sm leading-relaxed text-text-secondary">
            {result.narrative}
          </p>
        ) : (
          <p className="mt-6 text-sm leading-relaxed text-text-muted">
            The written summary isn't available right now. The numbers and
            recommendations below are still accurate.
          </p>
        )}
      </section>

      <section>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="border border-border bg-surface p-4">
            <p className="text-xl font-semibold text-text">
              {metrics.common_count}
            </p>
            <p className="mt-1 text-xs text-text-muted">Films in common</p>
          </div>

          <div className="border border-border bg-surface p-4">
            <p className="text-xl font-semibold text-text">
              {similarity !== null ? `${similarity}%` : "–"}
            </p>
            <p className="mt-1 text-xs text-text-muted">Taste similarity</p>
          </div>

          <div className="border border-border bg-surface p-4">
            <p className="text-xl font-semibold text-text">
              {metrics.mean_rating_gap !== null
                ? metrics.mean_rating_gap.toFixed(1)
                : "–"}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Average rating gap (of 5)
            </p>
          </div>

          <div className="border border-border bg-surface p-4">
            <p className="text-xl font-semibold text-text">
              {metrics.library_sizes[youKey] ?? 0} /{" "}
              {metrics.library_sizes[partnerKey] ?? 0}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Films: you / friend
            </p>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-text">
          You both loved
        </h2>

        <p className="mt-1 text-sm text-text-muted">
          Films you both rated highly.
        </p>

        <ComparisonMovieGrid
          entries={metrics.agreements}
          youKey={youKey}
          partnerKey={partnerKey}
          emptyText="No films that you both rated highly yet."
        />
      </section>

      <section>
        <h2 className="text-lg font-semibold text-text">
          Where you disagree
        </h2>

        <p className="mt-1 text-sm text-text-muted">
          Films where your ratings differ the most.
        </p>

        <ComparisonMovieGrid
          entries={metrics.divergences}
          youKey={youKey}
          partnerKey={partnerKey}
          emptyText="No big disagreements on the films you've both rated."
        />
      </section>

      <section>
        <h2 className="text-lg font-semibold text-text">
          Watch these together
        </h2>

        <p className="mt-1 text-sm text-text-muted">
          Films neither of you has seen, picked for both tastes.
        </p>

        {recommendations.length === 0 ? (
          <p className="mt-3 text-sm text-text-muted">
            No joint recommendations available yet.
          </p>
        ) : (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {recommendations.map((rec) => {
              const youFit = toPercent(rec.per_user[youKey]);
              const friendFit = toPercent(rec.per_user[partnerKey]);

              return (
                <article
                  key={rec.movie_id}
                  className="border border-border bg-surface p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h3 className="text-xl font-semibold leading-snug text-text">
                        {rec.title}
                      </h3>

                      {rec.release_year && (
                        <p className="mt-1 text-sm text-text-muted">
                          {rec.release_year}
                        </p>
                      )}
                    </div>

                    <div className="shrink-0 text-right">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                        Taste fit
                      </p>

                      <div className="mt-1 flex items-center gap-2 text-xs text-text-secondary">
                        <span>You {youFit ?? "–"}%</span>
                        <span className="text-border">·</span>
                        <span>Friend {friendFit ?? "–"}%</span>
                      </div>
                    </div>
                  </div>

                  {rec.genres.length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {rec.genres.map((genre) => (
                        <span
                          key={genre}
                          className="border border-border bg-background px-2 py-1 text-[11px] text-text-muted"
                        >
                          {genre}
                        </span>
                      ))}
                    </div>
                  )}

                  {rec.justification && (
                    <section className="mt-5 border-t border-border pt-4">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                        Why this movie
                      </h4>

                      <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                        {rec.justification}
                      </p>
                    </section>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}