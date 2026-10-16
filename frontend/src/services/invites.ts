import { apiFetch } from "./api";

export const INVITE_TYPES = {
  COMPARISON: "COMPARISON",
  PAIRED_SWIPE: "PAIRED_SWIPE",
} as const;

export type InviteType = (typeof INVITE_TYPES)[keyof typeof INVITE_TYPES];

export interface AcceptInviteResponse {
  invite: { code?: string; type: string };
  target: { id: string; type: string };
}

const TARGET_PATHS: Record<InviteType, (id: string) => string> = {
  COMPARISON: (id) => `/comparison/room/${id}`,
  PAIRED_SWIPE: (id) => `/discover/together/${id}`,
};

export function inviteTargetPath({ target }: AcceptInviteResponse): string {
  const buildPath = TARGET_PATHS[target.type as InviteType];

  if (!buildPath) {
    throw new Error(`Unsupported invite type: ${target.type}`);
  }

  return buildPath(target.id);
}

export async function acceptInvite(code: string): Promise<AcceptInviteResponse> {
  const response = await apiFetch(
    `/api/invites/${encodeURIComponent(code)}/accept/`,
    { method: "POST" },
  );
  return response.json();
}