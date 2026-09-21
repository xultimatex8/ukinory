import { apiFetch } from "./api";

export interface ImportResult {
  missing: string[];
}

export async function importExport(
  files: File[],
): Promise<ImportResult> {
  const formData = new FormData();

  if (files.length === 1 && files[0].name.toLowerCase().endsWith(".zip")) {
    formData.append("file", files[0]);
  } else {
    files.forEach((file) => {
      formData.append("files", file);
    });
  }

  const response = await apiFetch("/api/imports/letterboxd/", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token")}`,
    },
    body: formData,
  });

  const result = await response.json();

  if (!response.ok) {
    throw result;
  }

  return result;
}
