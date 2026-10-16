import type { MovieRecommendation } from "../services/swipeSessions";

interface GenreChipsProps {
  genres: MovieRecommendation["genres"];
  className?: string;
  chipClassName: string;
}

export default function GenreChips({
  genres,
  className = "",
  chipClassName,
}: GenreChipsProps) {
  if (genres.length === 0) return null;

  return (
    <div className={`flex flex-wrap ${className}`}>
      {genres.map((genre) => (
        <span key={genre.tmdb_id} className={chipClassName}>
          {genre.name}
        </span>
      ))}
    </div>
  );
}