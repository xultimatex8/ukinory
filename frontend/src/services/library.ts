import { downloadBlob } from "../utils/download";
import { apiFetch } from "./api";

export interface LibraryStats {
  rated_total: number;
  rated_with_embedding: number;
}

export interface RateMoviePayload {
  rating?: number | null;
  liked?: boolean;
  watched_date?: string | null;
}

export async function checkLibraryData(): Promise<boolean> {
  const response = await apiFetch("/api/library/has-film-data/", {
    method: "GET",
  });

  return response.json();
}

export async function getLibraryStats(): Promise<LibraryStats> {
  const response = await apiFetch("/api/library/stats/", {
    method: "GET",
  });

  return response.json();
}

export async function rateMovie(
  movieId: number,
  payload: RateMoviePayload,
): Promise<void> {
  await apiFetch(`/api/library/movies/${movieId}/rating/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function exportWatchlistCsv(): Promise<void> {
  const response = await apiFetch("/api/library/watchlist/export/", {
    method: "GET",
  });

  downloadBlob(await response.blob(), "ukinory_full_watchlist.csv");
}