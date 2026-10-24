import { ApiError, apiFetch } from "./api";

export interface ImportResult {
  missing: string[];
}

export type ImportJobStatus = "pending" | "running" | "succeeded" | "failed";

interface EnqueueResponse {
  job_id: number;
  status: ImportJobStatus;
  status_url: string;
}

interface JobStatusResponse {
  job_id: number;
  status: ImportJobStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result?: { missing: string[]; [key: string]: unknown };
  error?: string;
}

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_MS = 15 * 60 * 1000;

export async function importExport(
  files: File[],
  onStatusChange?: (status: ImportJobStatus) => void,
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
    body: formData,
  });

  const job = (await response.json()) as EnqueueResponse;
  onStatusChange?.(job.status);

  return pollForResult(job, onStatusChange);
}

async function pollForResult(
  job: EnqueueResponse,
  onStatusChange?: (status: ImportJobStatus) => void,
): Promise<ImportResult> {
  const deadline = Date.now() + MAX_POLL_MS;

  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));

    const response = await apiFetch(job.status_url);
    const payload = (await response.json()) as JobStatusResponse;

    onStatusChange?.(payload.status);

    if (payload.status === "succeeded") {
      return { missing: payload.result?.missing ?? [] };
    }

    if (payload.status === "failed") {
      throw new ApiError(500, payload.error ?? "The import failed.");
    }
  }

  throw new ApiError(
    504,
    "The import is taking longer than expected. It's still running in " +
      "the background -- check back in a bit.",
  );
}