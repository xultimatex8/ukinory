import { apiFetch } from "./api";

export interface AcceptInviteResponse {
  invite: { code?: string; type: string };
  target: { id: string; type: string };
}

export async function acceptInvite(code: string): Promise<AcceptInviteResponse> {
  const response = await apiFetch(
    `/api/invites/${encodeURIComponent(code)}/accept/`,
    { method: "POST" },
  );
  return response.json();
}