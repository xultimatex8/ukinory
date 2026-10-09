import { useState } from "react";
import type { ReactNode } from "react";
import {
  Check,
  Download,
  ExternalLink,
  Film,
  Heart,
  Loader2,
  Plus,
  Scale,
  Sparkles,
  Star,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type {
  ComparisonEntry,
  ComparisonResult,
} from "../services/comparisons";
import { useRecommendationWatchlist } from "../hooks/useRecommendationWatchlist";

interface ComparisonResultViewProps {
  result: ComparisonResult;
  currentUserId: number | string | null;
  roomId: string;
}

type CardLayout = "vertical" | "horizontal";

const MOVIE_GRID_CLASS =
  "mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5";

function letterboxdUrl(tmdbId: number | string | null | undefined): string | null {
  if (tmdbId === null || tmdbId === undefined || tmdbId === "") return null;
  return `https://letterboxd.com/tmdb/${encodeURIComponent(String(tmdbId))}`;
}

function toPercent(value: number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

function MovieGrid({
  count,
  children,
}: {
  count: number;
  children: (layout: CardLayout) => ReactNode;
}) {
  if (count >= 5) {
    return <div className={MOVIE_GRID_CLASS}>{children("vertical")}</div>;
  }

  if (count === 4) {
    return (
      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {children("vertical")}
      </div>
    );
  }

  if (count === 3) {
    return (
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {children("horizontal")}
      </div>
    );
  }

  if (count === 2) {
    return (
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:max-w-3xl">
        {children("horizontal")}
      </div>
    );
  }

  return (
    <div className="mt-4 grid grid-cols-1 gap-4 sm:max-w-md">
      {children("horizontal")}
    </div>
  );
}

function EmptyState({
  icon: Icon,
  title,
  text,
}: {
  icon: LucideIcon;
  title: string;
  text: string;
}) {
  return (
    <div className="mt-4 flex flex-col items-center gap-2 border border-dashed border-border bg-surface/50 px-6 py-8 text-center">
      <Icon
        size={24}
        strokeWidth={1.5}
        className="text-text-muted"
        aria-hidden="true"
      />
      <p className="text-sm font-medium text-text">{title}</p>
      <p className="max-w-sm text-xs leading-relaxed text-text-muted">
        {text}
      </p>
    </div>
  );
}

function MoviePoster({
  url,
  title,
  layout,
}: {
  url?: string;
  title: string;
  layout: CardLayout;
}) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(url) && !failed;

  if (layout === "horizontal") {
    return (
      <div className="relative min-h-36 w-24 shrink-0 overflow-hidden border-r border-border bg-background sm:w-28">
        {showImage ? (
          <img
            src={url}
            alt={`Poster of ${title}`}
            loading="lazy"
            onError={() => setFailed(true)}
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-text-muted">
            <Film size={28} strokeWidth={1.5} aria-hidden="true" />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="aspect-2/3 w-full overflow-hidden border-b border-border bg-background">
      {showImage ? (
        <img
          src={url}
          alt={`Poster of ${title}`}
          loading="lazy"
          onError={() => setFailed(true)}
          className="h-full w-full object-cover"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-text-muted">
          <Film size={28} strokeWidth={1.5} aria-hidden="true" />
        </div>
      )}
    </div>
  );
}

function MovieHeading({
  title,
  year,
  reserveSpace,
}: {
  title: string;
  year: number | null;
  reserveSpace: boolean;
}) {
  return (
    <div>
      <h3
        className={`line-clamp-2 text-sm font-semibold leading-5 text-text ${
          reserveSpace ? "min-h-10" : ""
        }`}
        title={title}
      >
        {title}
      </h3>

      <p className={`mt-1 text-xs text-text-muted ${reserveSpace ? "h-4" : ""}`}>
        {year ?? ""}
      </p>
    </div>
  );
}

function UserLabel({ name, isYou }: { name: string; isYou: boolean }) {
  return (
    <span
      className="flex min-w-0 items-baseline justify-center gap-1"
      title={isYou ? `${name} (You)` : name}
    >
      <span className="truncate">{name}</span>
      {isYou && <span className="shrink-0">(You)</span>}
    </span>
  );
}

function PairStatValue({
  children,
  withStar,
}: {
  children: string;
  withStar: boolean;
}) {
  return (
    <p className="mt-0.5 inline-flex items-center justify-center gap-1 text-sm font-semibold text-text">
      {withStar && (
        <Star
          size={12}
          fill="currentColor"
          className="text-primary"
          aria-hidden="true"
        />
      )}
      {children}
    </p>
  );
}

function PairStat({
  caption,
  youLabel,
  partnerLabel,
  youValue,
  partnerValue,
  withStar = false,
}: {
  caption: string;
  youLabel: ReactNode;
  partnerLabel: ReactNode;
  youValue: string;
  partnerValue: string;
  withStar?: boolean;
}) {
  return (
    <div className="mt-auto border-t border-border">
      <p className="pt-2 text-center text-[10px] font-semibold uppercase tracking-wider text-text-muted">
        {caption}
      </p>

      <div className="grid grid-cols-2 divide-x divide-border pb-2.5 pt-1 text-center">
        <div className="min-w-0 px-3">
          <p className="text-[11px] text-text-muted">{youLabel}</p>
          <PairStatValue withStar={withStar}>{youValue}</PairStatValue>
        </div>

        <div className="min-w-0 px-3">
          <p className="text-[11px] text-text-muted">{partnerLabel}</p>
          <PairStatValue withStar={withStar}>{partnerValue}</PairStatValue>
        </div>
      </div>
    </div>
  );
}

function WatchlistButton({
  title,
  saved,
  pending,
  onClick,
}: {
  title: string;
  saved: boolean;
  pending: boolean;
  onClick: () => void;
}) {
  const Icon = pending ? Loader2 : saved ? Check : Plus;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      aria-pressed={saved}
      aria-label={
        saved
          ? `Remove ${title} from your watchlist`
          : `Add ${title} to your watchlist`
      }
      className={`cursor-pointer flex w-full items-center justify-center gap-1.5 border-t border-border px-3 py-2 text-xs font-medium transition-colors disabled:opacity-60 ${
        saved
          ? "bg-primary/10 text-primary hover:bg-primary/20"
          : "text-text-secondary hover:bg-background hover:text-primary"
      }`}
    >
      <Icon
        size={14}
        aria-hidden="true"
        className={pending ? "animate-spin" : ""}
      />
      {saved ? "In your watchlist" : "Add to watchlist"}
    </button>
  );
}

function MovieCard({
  title,
  year,
  posterUrl,
  genres,
  justification,
  layout,
  tmdbId,
  action,
  children,
}: {
  title: string;
  year: number | null;
  posterUrl?: string;
  tmdbId?: number | string | null;
  genres?: string[];
  justification?: string;
  layout: CardLayout;
  action?: ReactNode;
  children: ReactNode;
}) {
  const isHorizontal = layout === "horizontal";
  const href = letterboxdUrl(tmdbId);

  const body = (
    <>
      <div className="p-3">
        <MovieHeading title={title} year={year} reserveSpace={!isHorizontal} />

        {genres && genres.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {genres.map((genre) => (
              <span
                key={genre}
                className="border border-border bg-background px-1.5 py-0.5 text-[10px] text-text-muted"
              >
                {genre}
              </span>
            ))}
          </div>
        )}

        {justification && (
          <p className="mt-3 border-t border-border pt-3 text-xs leading-relaxed text-text-secondary">
            {justification}
          </p>
        )}
      </div>

      {children}

      {action}

      {href && (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`View ${title} on Letterboxd`}
          className="flex items-center justify-center gap-1.5 border-t border-border px-3 py-2 text-xs font-medium text-text-secondary transition-colors hover:bg-background hover:text-primary"
        >
          View on Letterboxd
          <ExternalLink size={12} aria-hidden="true" />
        </a>
      )}
    </>
  );

  if (isHorizontal) {
    return (
      <article className="flex overflow-hidden border border-border bg-surface">
        <MoviePoster url={posterUrl} title={title} layout={layout} />
        <div className="flex min-w-0 flex-1 flex-col">{body}</div>
      </article>
    );
  }

  return (
    <article className="flex flex-col overflow-hidden border border-border bg-surface">
      <MoviePoster url={posterUrl} title={title} layout={layout} />
      {body}
    </article>
  );
}

function ComparisonMovieGrid({
  entries,
  youKey,
  partnerKey,
  youLabel,
  partnerLabel,
  empty,
}: {
  entries: ComparisonEntry[];
  youKey: string;
  partnerKey: string;
  youLabel: ReactNode;
  partnerLabel: ReactNode;
  empty: ReactNode;
}) {
  if (entries.length === 0) return <>{empty}</>;

  return (
    <MovieGrid count={entries.length}>
      {(layout) =>
        entries.map((entry) => (
          <MovieCard
            key={`${entry.title}-${entry.release_year}`}
            title={entry.title}
            year={entry.release_year}
            posterUrl={entry.poster_url}
            tmdbId={entry.tmdb_id}
            layout={layout}
          >
            <PairStat
              caption="Ratings"
              withStar
              youLabel={youLabel}
              partnerLabel={partnerLabel}
              youValue={String(entry.ratings[youKey] ?? "–")}
              partnerValue={String(entry.ratings[partnerKey] ?? "–")}
            />
          </MovieCard>
        ))
      }
    </MovieGrid>
  );
}

export default function ComparisonResultView({
  result,
  currentUserId,
  roomId,
}: ComparisonResultViewProps) {
  const { metrics, recommendations } = result;

  const watchlist = useRecommendationWatchlist(roomId, recommendations);

  const keys = Object.keys(metrics.library_sizes);

  const viewerId =
    result.current_user_id ??
    (currentUserId !== null ? String(currentUserId) : null);

  const isCurrentUserKnown = viewerId !== null && keys.includes(viewerId);
  const youKey = isCurrentUserKnown ? viewerId : (keys[0] ?? "");
  const partnerKey = keys.find((key) => key !== youKey) ?? "";

  const youNarrative = result.individual_narratives?.[youKey] ?? "";
  const partnerNarrative = result.individual_narratives?.[partnerKey] ?? "";

  const youUsername = result.participants?.[youKey];
  const partnerUsername = result.participants?.[partnerKey];
  const youName = youUsername ?? "You";
  const partnerName = partnerUsername ?? "Your friend";
  const showYouTag = isCurrentUserKnown && youUsername !== undefined;

  const youLabel = <UserLabel name={youName} isYou={showYouTag} />;
  const partnerLabel = <UserLabel name={partnerName} isYou={false} />;

  const score = metrics.compatibility_score;
  const similarity = toPercent(metrics.taste_similarity);
  const hasCommonFilms = metrics.common_count > 0;

  return (
    <div className="space-y-8">
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

        {result.narrative_available &&
          (youNarrative || partnerNarrative) && (
            <div className="mt-6 grid border-t border-border pt-6 md:grid-cols-2">
              <div className="min-w-0">
                <h3 className="flex min-w-0 items-baseline gap-1 text-sm font-semibold text-text">
                  <span className="truncate" title={youName}>
                    {youName}
                  </span>
                  {showYouTag && (
                    <span className="shrink-0 font-normal text-text-muted">
                      (You)
                    </span>
                  )}
                </h3>
                <p className="pr-2 mt-2 text-sm leading-relaxed text-text-secondary">
                  {youNarrative}
                </p>
              </div>

              <div className="min-w-0 md:border-l md:border-border md:pl-4">
                <h3
                  className="truncate text-sm font-semibold text-text"
                  title={partnerName}
                >
                  {partnerName}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {partnerNarrative}
                </p>
              </div>
            </div>
          )}
      </section>

      <section>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="border border-border bg-surface p-4">
            <p className="text-xl font-semibold text-text">
              {metrics.common_count}
            </p>
            <p className="mt-1 text-xs text-text-muted">Movies in common</p>
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
            <p
              className="mt-1 truncate text-xs text-text-muted"
              title={`Movies: ${youName} / ${partnerName}`}
            >
              Movies: {youName} / {partnerName}
            </p>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-text">You both loved</h2>

        <p className="mt-1 text-sm text-text-muted">
          Movies you both rated highly.
        </p>

        <ComparisonMovieGrid
          entries={metrics.agreements}
          youKey={youKey}
          partnerKey={partnerKey}
          youLabel={youLabel}
          partnerLabel={partnerLabel}
          empty={
            <EmptyState
              icon={Heart}
              title={
                hasCommonFilms
                  ? "No shared favourites yet"
                  : "No movies in common yet"
              }
              text={
                hasCommonFilms
                  ? "There's no movie that you both rated 4 stars or higher. Rate more movies to find your overlap."
                  : "You haven't rated any of the same movies yet. Once you do, the ones you both love will show up here."
              }
            />
          }
        />
      </section>

      <section>
        <h2 className="text-lg font-semibold text-text">Where you disagree</h2>

        <p className="mt-1 text-sm text-text-muted">
          Movies where your ratings differ the most.
        </p>

        <ComparisonMovieGrid
          entries={metrics.divergences}
          youKey={youKey}
          partnerKey={partnerKey}
          youLabel={youLabel}
          partnerLabel={partnerLabel}
          empty={
            <EmptyState
              icon={Scale}
              title={
                hasCommonFilms
                  ? "No big disagreements"
                  : "Nothing to compare yet"
              }
              text={
                hasCommonFilms
                  ? "You're pretty much in sync: no movie has a rating gap of 1.5 stars or more."
                  : "Disagreements appear once you've both rated some of the same movies."
              }
            />
          }
        />
      </section>

      <section>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-text">
              Recommended for both of you
            </h2>

            <p className="mt-1 text-sm text-text-muted">
              Movies neither of you has seen, picked to match both of your
              tastes.
            </p>
          </div>

          {recommendations.length > 0 && (
            <button
              type="button"
              onClick={() => void watchlist.exportCsv()}
              disabled={watchlist.savedCount === 0 || watchlist.isExporting}
              title={
                watchlist.savedCount === 0
                  ? "Add some recommendations to your watchlist first"
                  : undefined
              }
              className="inline-flex items-center gap-2 border border-border bg-surface px-3 py-2 text-xs font-medium text-text-secondary transition-colors hover:border-primary hover:text-primary disabled:cursor-auto disabled:opacity-50 disabled:hover:border-border disabled:hover:text-text-secondary"
            >
              {watchlist.isExporting ? (
                <Loader2
                  size={14}
                  className="animate-spin"
                  aria-hidden="true"
                />
              ) : (
                <Download size={14} aria-hidden="true" />
              )}
              Export watchlist
              {watchlist.savedCount > 0 && ` (${watchlist.savedCount})`}
            </button>
          )}
        </div>

        {watchlist.error && (
          <p
            role="alert"
            className="mt-3 border border-red-400/40 bg-red-400/10 px-3 py-2 text-xs text-red-400"
          >
            {watchlist.error}
          </p>
        )}

        {recommendations.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="No joint recommendations yet"
            text="We couldn't find movies neither of you has seen that fit both tastes. Try again after rating more movies."
          />
        ) : (
          <MovieGrid count={recommendations.length}>
            {(layout) =>
              recommendations.map((rec) => {
                const youFit = toPercent(rec.per_user[youKey]);
                const friendFit = toPercent(rec.per_user[partnerKey]);

                return (
                  <MovieCard
                    key={rec.movie_id}
                    title={rec.title}
                    year={rec.release_year}
                    posterUrl={rec.poster_url}
                    tmdbId={rec.tmdb_id}
                    genres={rec.genres}
                    justification={rec.justification}
                    layout={layout}
                    action={
                      <WatchlistButton
                        title={rec.title}
                        saved={watchlist.isSaved(rec.movie_id)}
                        pending={watchlist.isPending(rec.movie_id)}
                        onClick={() => void watchlist.toggle(rec.movie_id)}
                      />
                    }
                  >
                    <PairStat
                      caption="Taste fit"
                      youLabel={youLabel}
                      partnerLabel={partnerLabel}
                      youValue={youFit !== null ? `${youFit}%` : "–"}
                      partnerValue={
                        friendFit !== null ? `${friendFit}%` : "–"
                      }
                    />
                  </MovieCard>
                );
              })
            }
          </MovieGrid>
        )}
      </section>
    </div>
  );
}