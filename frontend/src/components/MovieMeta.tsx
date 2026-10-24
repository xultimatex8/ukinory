import { Star } from "lucide-react";

import type { MovieRecommendation } from "../services/swipeSessions";
import { formatRuntime } from "../utils/movie";

interface MovieMetaProps {
  movie: MovieRecommendation;
  className?: string;
  starSize?: number;
}

export default function MovieMeta({
  movie,
  className = "",
  starSize = 14,
}: MovieMetaProps) {
  return (
    <div className={`flex flex-wrap items-center gap-y-1 ${className}`}>
      {movie.release_year ? <span>{movie.release_year}</span> : null}

      {movie.runtime ? <span>{formatRuntime(movie.runtime)}</span> : null}

      {movie.vote_average !== null && (
        <span className="inline-flex items-center gap-1">
          <Star size={starSize} fill="currentColor" />
          {movie.vote_average.toFixed(1)}
        </span>
      )}
    </div>
  );
}