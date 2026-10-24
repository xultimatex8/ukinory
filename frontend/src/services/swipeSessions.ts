import { apiFetch } from "./api";
import {
  buildSocketUrl,
  type Invite,
  type ParticipantState,
} from "./sessions";

export interface SwipeSession {
  id: string;
  type: string;
  status: string;
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

export interface MatchEvent {
  candidate_id: string;
  movie_id: string;
  tmdb_id: number;
  title: string;
  release_year: number | null;
}

export interface SwipeResult {
  matched: boolean;
  match: MatchEvent | null;
}

export interface PairedSessionState extends ParticipantState {
  type: string;
  current_user_id: string;
  matches_count: number;
}

export type PairedInvite = Invite;

export interface CreatePairedSessionResponse {
  session: PairedSessionState;
  invite: PairedInvite;
}

export interface SessionMatch {
  candidate_id: string;
  matched_at: string | null;
  movie: {
    tmdb_id: number;
    title: string;
    release_year: number | null;
    poster_url: string;
  };
}

interface JustificationResponse {
  justification: string | null;
  available: boolean;
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
): Promise<SwipeResult> {
  const response = await apiFetch(
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

  return response.json();
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

export async function leaveSwipeSession(sessionId: string): Promise<void> {
  await apiFetch(`/api/swipe-sessions/${sessionId}/leave/`, {
    method: "DELETE",
  });
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

export async function createPairedSwipeSession(): Promise<CreatePairedSessionResponse> {
  const response = await apiFetch("/api/swipe-sessions/paired/", {
    method: "POST",
  });

  return response.json();
}

export async function getPairedSessionState(
  sessionId: string,
): Promise<PairedSessionState> {
  const response = await apiFetch(`/api/swipe-sessions/${sessionId}/paired/`, {
    method: "GET",
  });

  return response.json();
}

export async function regeneratePairedInvite(
  sessionId: string,
): Promise<PairedInvite> {
  const response = await apiFetch(`/api/swipe-sessions/${sessionId}/invite/`, {
    method: "POST",
  });

  return response.json();
}

export async function getSessionMatches(
  sessionId: string,
): Promise<SessionMatch[]> {
  const response = await apiFetch(`/api/swipe-sessions/${sessionId}/matches/`, {
    method: "GET",
  });

  return response.json();
}

export function buildSessionSocketUrl(sessionId: string, token: string): string {
  return buildSocketUrl(`/ws/swipe-sessions/${sessionId}/`, token);
}