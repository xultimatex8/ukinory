import { wsUrl } from "../api";
import { ApiError } from "./api";

export type SessionStatus = "WAITING" | "ACTIVE" | "FINISHED";

export interface Invite {
  id?: string;
  code: string;
  type?: string;
  status?: string;
  expires_at: string;
}

export interface ParticipantState {
  id: string;
  status: SessionStatus;
  participants: number;
  partner_joined: boolean;
  you_have_data: boolean;
  partner_has_data: boolean | null;
}

export type FatalSessionError = "not_found" | "forbidden" | "closed";

export function classifyFatalError(err: unknown): FatalSessionError | null {
  if (!(err instanceof ApiError)) return null;

  switch (err.status) {
    case 404:
      return "not_found";
    case 403:
      return "forbidden";
    case 410:
      return "closed";
    default:
      return null;
  }
}

export function buildSocketUrl(path: string, token: string): string {
  const url = new URL(wsUrl(path));
  url.searchParams.set("token", token);
  return url.toString();
}