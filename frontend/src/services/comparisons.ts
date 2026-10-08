import { apiFetch } from "./api";
import { apiUrl } from "../api";

const COMPARISONS_PATH = "/api/comparisons";
const ROOMS_PATH = COMPARISONS_PATH + "/comparison-rooms";

export type GenerationStatus =
  | "pending"
  | "running"
  | "ready"
  | "needs_data"
  | "failed";

export interface Invite {
  id?: string;
  code: string;
  type?: string;
  status?: string;
  expires_at: string;
}

export interface RoomState {
  id: string;
  status: "WAITING" | "ACTIVE" | "FINISHED";
  participants: number;
  partner_joined: boolean;
  comparison_id: string | null;
  generation_status: GenerationStatus | null;
  you_have_data: boolean;
  partner_has_data: boolean | null;
}

export interface CreateRoomResponse {
  room: RoomState;
  invite: Invite;
}

export interface ComparisonEntry {
  movie_id: number | string | null;
  title: string;
  release_year: number | null;
  ratings: Record<string, number | null>;
  poster_url?: string;
  tmdb_id?: number | string | null;
}

export interface ComparisonMetrics {
  compatibility_score: number | null;
  taste_similarity: number | null;
  library_sizes: Record<string, number>;
  common_count: number;
  overlap_ratio: number | null;
  jaccard: number | null;
  mean_rating_gap: number | null;
  rating_correlation: number | null;
  agreements: ComparisonEntry[];
  divergences: ComparisonEntry[];
}

export interface JointRecommendation {
  movie_id: number | string;
  title: string;
  release_year: number | null;
  genres: string[];
  score: number;
  per_user: Record<string, number>;
  justification: string;
  poster_url?: string;
  tmdb_id?: number | string | null;
}

export interface ComparisonResult {
  id: string;
  generated_at: string | null;
  metrics: ComparisonMetrics;
  narrative: string;
  individual_narratives?: Record<string, string>;
  current_user_id: string;
  participants?: Record<string, string>;
  narrative_available: boolean;
  recommendations: JointRecommendation[];
}

export async function createComparisonRoom(): Promise<CreateRoomResponse> {
  const response = await apiFetch(`${ROOMS_PATH}/`, { method: "POST" });
  return response.json();
}

export async function getRoom(roomId: string): Promise<RoomState> {
  const response = await apiFetch(`${ROOMS_PATH}/${roomId}/`, {
    method: "GET",
  });
  return response.json();
}

export async function regenerateInvite(roomId: string): Promise<Invite> {
  const response = await apiFetch(`${ROOMS_PATH}/${roomId}/invite/`, {
    method: "POST",
  });
  return response.json();
}

export async function generateComparison(roomId: string): Promise<RoomState> {
  const response = await apiFetch(`${COMPARISONS_PATH}/${roomId}/generate/`, {
    method: "POST",
  });
  return response.json();
}

export async function getComparisonResult(
  roomId: string,
): Promise<ComparisonResult> {
  const response = await apiFetch(`${COMPARISONS_PATH}/${roomId}/result/`, {
    method: "GET",
  });
  return response.json();
}

export function buildRoomSocketUrl(roomId: string, token: string): string {
  const url = new URL(
    String(apiUrl(`/ws/comparison-rooms/${roomId}/`)),
    window.location.href,
  );
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("token", token);
  return url.toString();
}