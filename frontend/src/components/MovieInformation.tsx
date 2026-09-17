import { useState } from "react";
import { Star } from "lucide-react";
import type { MovieRecommendation } from "../services/swipeSessions";
import type { StreamingCountry } from "./StreamingProviders";

interface MovieInformationProps {
  movie: MovieRecommendation | null;
  streamingCountries: StreamingCountry[];
}

export default function MovieInformation({
  movie,
  streamingCountries,
}: MovieInformationProps) {
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);

  const defaultCountry =
    streamingCountries.find((country) => country.code === "ES") ??
    streamingCountries[0];

  const selectedCountryData =
    streamingCountries.find(
      (country) => country.code === selectedCountry,
    ) ?? defaultCountry;

  return (
    <aside className="hidden w-72 shrink-0 lg:block">
      <div className="border border-border bg-surface p-6">
        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          Movie information
        </p>

        {movie ? (
          <>
            <h3 className="mt-4 text-xl font-semibold leading-snug text-text">
              {movie.title}
            </h3>

            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-muted">
              {movie.release_year && (
                <span>{movie.release_year}</span>
              )}

              {movie.runtime && (
                <span>
                  {Math.floor(movie.runtime / 60)}h{" "}
                  {movie.runtime % 60} min
                </span>
              )}

              {movie.vote_average !== null && (
                <span className="inline-flex items-center gap-1">
                  <Star size={13} fill="currentColor" />
                  {movie.vote_average.toFixed(1)}
                </span>
              )}
            </div>

            {movie.genres.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1.5">
                {movie.genres.map((genre) => (
                  <span
                    key={genre.tmdb_id}
                    className="border border-border bg-background px-2 py-1 text-[11px] text-text-muted"
                  >
                    {genre.name}
                  </span>
                ))}
              </div>
            )}

            {movie.synopsis && (
              <section className="mt-6 border-t border-border pt-5">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                  Synopsis
                </h4>

                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {movie.synopsis}
                </p>
              </section>
            )}

            <section className="mt-6 border-t border-border pt-5">
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                  Where to watch
                </h4>

                {streamingCountries.length > 0 && (
                  <select
                    value={selectedCountry ?? defaultCountry?.code ?? ""}
                    onChange={(event) =>
                      setSelectedCountry(event.target.value)
                    }
                    className="max-w-24 cursor-pointer border border-border bg-background px-2 py-1 text-[10px] text-text-secondary outline-none focus:border-primary"
                    aria-label="Select country"
                  >
                    {streamingCountries.map((country) => (
                      <option key={country.code} value={country.code}>
                        {country.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {selectedCountryData ? (
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {selectedCountryData.providers.map((provider) => (
                    <div
                      key={provider.id}
                      className="flex min-w-0 flex-col items-center border border-border bg-background px-2 py-2.5"
                      title={provider.name}
                    >
                      <img
                        src={provider.logoUrl}
                        alt={provider.name}
                        className="h-9 w-9 rounded object-cover"
                      />

                      <span className="mt-1.5 line-clamp-2 w-full text-center text-[10px] leading-tight text-text-muted">
                        {provider.name}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-text-muted">
                  No streaming information available.
                </p>
              )}
            </section>

            <a
              href={`https://letterboxd.com/tmdb/${movie.tmdb_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-6 flex w-full items-center justify-center border border-border bg-background px-3 py-2.5 text-xs font-semibold text-text-secondary transition-colors hover:border-primary hover:text-primary"
            >
              View on Letterboxd
            </a>
          </>
        ) : (
          <div className="mt-6">
            <div className="h-4 w-32 bg-background" />
            <div className="mt-3 h-3 w-24 bg-background" />
            <div className="mt-6 h-3 w-20 bg-background" />
            <div className="mt-3 h-12 w-full bg-background" />
          </div>
        )}
      </div>
    </aside>
  );
}