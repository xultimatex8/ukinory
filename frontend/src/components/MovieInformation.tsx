import type { MovieRecommendation } from "../services/swipeSessions";
import MovieDetails from "./MovieDetails";
import type { StreamingCountry } from "./StreamingProviders";

interface MovieInformationProps {
  movie: MovieRecommendation | null;
  streamingCountries: StreamingCountry[];
}

export default function MovieInformation({
  movie,
  streamingCountries,
}: MovieInformationProps) {
  return (
    <aside className="hidden w-72 shrink-0 lg:block">
      <div className="border border-border bg-surface p-6">
        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          Movie information
        </p>

        {movie ? (
          <MovieDetails
            movie={movie}
            streamingCountries={streamingCountries}
            variant="sidebar"
          />
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