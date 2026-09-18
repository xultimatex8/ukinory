import type { User } from "./user";

export interface RegisterData {
  email: string;
  username: string;
  password: string;
}

export interface AuthResponse {
  user: User;
  access: string;
  refresh: string;
}

export async function register(
  data: RegisterData,
): Promise<AuthResponse> {
  const response = await fetch("/api/auth/register/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  const result = await response.json();

  if (!response.ok) {
    throw result;
  }

  return result;
}

export async function login(data: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  const response = await fetch("/api/auth/token/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  const result = await response.json();

  if (!response.ok) {
    throw result;
  }

  return result;
}

export async function createGuest(): Promise<AuthResponse> {
  const response = await fetch("/api/auth/guest/", {
    method: "POST",
  });

  const result = await response.json();

  if (!response.ok) {
    throw result;
  }

  return result;
}