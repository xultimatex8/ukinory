import { apiFetch } from "./api";

export async function checkLibraryData(): Promise<boolean> {
  const response = await apiFetch("/api/library/has-film-data/", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token")}`,
    },
  });

  const result = await response.json();

  if (!response.ok) {
    throw result;
  }

  return result;
}