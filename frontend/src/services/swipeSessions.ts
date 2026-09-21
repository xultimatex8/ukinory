import { apiFetch } from "./api";

export interface SwipeSession {
  id: string;
  type: string;
  status: string;
  leave_token: string | null;
}

export interface MovieRecommendation {
  tmdb_id: number;
  title: string;
  release_year: number | null;
  synopsis: string;
  poster_url: string;
  vote_average: number | null;
  runtime: number | null;
  streaming_providers: Record<string, unknown>;
  genres: {
    tmdb_id: number;
    name: string;
  }[];
}

export interface RecommendationResponse {
  finished: boolean;
  candidate_id: string | null;
  movie: MovieRecommendation | null;
}

export interface JustificationResponse {
  justification: string;
}

export async function createIndividualSwipeSession(): Promise<SwipeSession> {
  const response = await apiFetch("/api/swipe-sessions/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      type: "INDIVIDUAL",
    }),
  });

  return response.json();
}

export async function startSwipeSession(
  sessionId: string,
): Promise<SwipeSession> {
  const response = await apiFetch(
    `/api/swipe-sessions/${sessionId}/start/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    },
  );

  return response.json();
}

export async function getSwipeRecommendation(
  sessionId: string,
): Promise<RecommendationResponse> {
  const response = await apiFetch(
    `/api/swipe-sessions/${sessionId}/recommendation/`,
    {
      method: "GET",
    },
  );

  return response.json();
}

export async function getRecommendationJustification(
  sessionId: string,
  candidateId: string,
): Promise<JustificationResponse> {
  const response = await apiFetch(
    `/api/swipe-sessions/${sessionId}/candidates/${candidateId}/justification/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    },
  );

  return response.json();
}

export async function recordSwipe(
  sessionId: string,
  candidateId: string,
  action: "SKIP" | "WATCHLIST",
): Promise<void> {
  await apiFetch(
    `/api/swipe-sessions/${sessionId}/swipe/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        candidate_id: candidateId,
        action,
      }),
    },
  );
}

export async function endSwipeSession(
  sessionId: string,
): Promise<Blob> {
  const response = await apiFetch(
    `/api/swipe-sessions/${sessionId}/end/`,
    {
      method: "POST",
    },
  );

  return response.blob();
}

export async function getSwipeSession(
  sessionId: string,
): Promise<SwipeSession> {
  const response = await apiFetch(`/api/swipe-sessions/${sessionId}/`, {
    method: "GET",
  });

  return response.json();
}

export async function sendHeartbeat(sessionId: string): Promise<void> {
  try {
    await apiFetch(`/api/swipe-sessions/${sessionId}/heartbeat/`, {
      method: "POST",
    });
  } catch {
    // The next heartbeat will retry.
  }
}