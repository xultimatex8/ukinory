import { apiFetch } from "./api";

export interface LibraryStats {
  rated_total: number;
  rated_with_embedding: number;
}

export async function checkLibraryData(): Promise<boolean> {
  const response = await apiFetch("/api/library/has-film-data/", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token")}`,
    },
  });

  return response.json();
}

export async function getLibraryStats(): Promise<LibraryStats> {
  const response = await apiFetch("/api/library/stats/", {
    method: 'GET',
  });
 
  return await response.json();
}