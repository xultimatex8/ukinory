export function formatRuntime(minutes: number): string {
  return `${Math.floor(minutes / 60)}h ${minutes % 60} min`;
}

export function letterboxdUrl(tmdbId: number | string): string {
  return `https://letterboxd.com/tmdb/${encodeURIComponent(String(tmdbId))}`;
}