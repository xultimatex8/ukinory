import { apiFetch } from "./api";
import type { LegalDocumentId } from "./legal";

export interface User {
  id: number;
  email: string;
  username: string;
  is_guest: boolean;
}

export interface AuthResponse {
  user: User;
  access: string;
  refresh: string;
}

export async function getCurrentUser(): Promise<User> {
  const response = await apiFetch("/api/auth/me/", {
    method: "GET",
  });

  return response.json();
}

export async function updateUser(data: {
  email: string;
  username: string;
}): Promise<User> {
  const response = await apiFetch("/api/auth/me/", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  return response.json();
}

export async function changePassword(data: {
  oldPassword: string;
  newPassword: string;
}): Promise<void> {
  await apiFetch("/api/auth/me/password/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      old_password: data.oldPassword,
      new_password: data.newPassword,
    }),
  });
}

export async function claimGuest(data: {
  email: string;
  username?: string;
  password: string;
  accepted_documents: LegalDocumentId[];
}): Promise<AuthResponse> {
  const response = await apiFetch("/api/auth/guest/claim/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  return response.json();
}

export async function signOut(): Promise<void> {
  const refreshToken = localStorage.getItem("refresh_token");

  if (!refreshToken) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    return;
  }

  try {
    await apiFetch("/api/auth/logout/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh: refreshToken,
      }),
    });
  } finally {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }
}

export async function deleteAccount(password?: string): Promise<void> {
  await apiFetch("/api/auth/me/delete/", {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(
      password
        ? {
            password,
          }
        : {},
    ),
  });
}

export async function exportUserData(): Promise<void> {
  const response = await apiFetch("/api/auth/me/export/", {
    method: "GET",
  });

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = `account-data-${Date.now()}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();

  window.URL.revokeObjectURL(url);
}