import { apiFetch } from "./api";

export async function checkLibraryData(): Promise<boolean> {
  const response = await apiFetch("/api/library/has-film-data/", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token")}`,
    },
  });

  return response.json();
}