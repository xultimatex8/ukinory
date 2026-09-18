import { apiFetch } from "./api";

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

export async function claimGuest(data: {
  email: string;
  username?: string;
  password: string;
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