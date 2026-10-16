import type { MovieRecommendation } from "../services/swipeSessions";
import { letterboxdUrl } from "../utils/movie";
import GenreChips from "./GenreChips";
import MovieMeta from "./MovieMeta";
import type { StreamingCountry } from "./StreamingProviders";
import WhereToWatch from "./WhereToWatch";

type Variant = "sidebar" | "modal";

const STYLES = {
  sidebar: {
    title: "mt-4 text-xl",
    meta: "mt-3 gap-x-3 text-sm text-text-muted",
    starSize: 13,
    genres: "mt-4 gap-1.5",
    genreChip:
      "border border-border bg-background px-2 py-1 text-[11px] text-text-muted",
    synopsisSection: "mt-6 border-t border-border pt-5",
    synopsis: "mt-2 line-clamp-7 text-sm leading-relaxed text-text-secondary",
    whereToWatch: "compact",
  },
  modal: {
    title: "text-2xl",
    meta: "mt-3 gap-x-4 text-sm text-text-muted",
    starSize: 14,
    genres: "mt-5 gap-1.5",
    genreChip:
      "border border-border bg-background px-2.5 py-1 text-xs text-text-muted",
    synopsisSection: "mt-7 border-t border-border pt-5",
    synopsis: "mt-2 text-sm leading-relaxed text-text-secondary",
    whereToWatch: "regular",
  },
} as const;

interface MovieDetailsProps {
  movie: MovieRecommendation;
  streamingCountries: StreamingCountry[];
  variant: Variant;
}

export default function MovieDetails({
  movie,
  streamingCountries,
  variant,
}: MovieDetailsProps) {
  const styles = STYLES[variant];

  return (
    <>
      <h3 className={`${styles.title} font-semibold leading-snug text-text`}>
        {movie.title}
      </h3>

      <MovieMeta
        movie={movie}
        className={styles.meta}
        starSize={styles.starSize}
      />

      <GenreChips
        genres={movie.genres}
        className={styles.genres}
        chipClassName={styles.genreChip}
      />

      {movie.synopsis && (
        <section className={styles.synopsisSection}>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Synopsis
          </h4>

          <p className={styles.synopsis}>{movie.synopsis}</p>
        </section>
      )}

      <WhereToWatch
        countries={streamingCountries}
        variant={styles.whereToWatch}
      />

      <a
        href={letterboxdUrl(movie.tmdb_id)}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-6 flex w-full items-center justify-center border border-border bg-background px-3 py-2.5 text-xs font-semibold text-text-secondary transition-colors hover:border-primary hover:text-primary"
      >
        View on Letterboxd
      </a>
    </>
  );
}