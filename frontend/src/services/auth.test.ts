import { afterEach, describe, expect, it, vi } from "vitest";
import { apiUrl } from "../api";
import { register, login, createGuest } from "./auth";
import type { AuthResponse } from "./auth";

function mockFetchResponse(
  body: unknown,
  ok = true,
  status = ok ? 201 : 400,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      json: vi.fn().mockResolvedValue(body),
    }),
  );
}

const authResponse = {
  user: {
    id: 1,
    email: "test@example.com",
    username: "testuser",
    is_guest: false,
  },
  access: "access-token",
  refresh: "refresh-token",
} satisfies AuthResponse;

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("register", () => {
  const data = {
    email: "test@example.com",
    username: "testuser",
    password: "Password123!",
    accepted_documents: ["terms"],
  };

  it("registers a user and returns the user data and tokens", async () => {
    mockFetchResponse(authResponse, true, 201);

    const result = await register(data);

    expect(fetch).toHaveBeenCalledWith(
      apiUrl("/api/auth/register/"),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      },
    );

    expect(result).toEqual(authResponse);
  });

  it("throws the validation errors returned by the backend", async () => {
    const error = {
      accepted_documents: [
        "You must accept the current legal documents.",
      ],
    };

    mockFetchResponse(error, false, 400);

    await expect(register(data)).rejects.toEqual(error);
  });

  it("throws an error when the email is already registered", async () => {
    const error = {
      email: ["A user with this email already exists."],
    };

    mockFetchResponse(error, false, 400);

    await expect(register(data)).rejects.toEqual(error);
  });
});

describe("login", () => {
  it("sends the credentials and returns the tokens", async () => {
    const data = {
      email: "test@example.com",
      password: "Password123!",
    };

    mockFetchResponse(authResponse, true, 200);

    const result = await login(data);

    expect(fetch).toHaveBeenCalledWith(
      apiUrl("/api/auth/token/"),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      },
    );

    expect(result).toEqual(authResponse);
  });

  it("throws the authentication error returned by the backend", async () => {
    const error = {
      detail: "No active account found with the given credentials",
    };

    mockFetchResponse(error, false, 401);

    await expect(
      login({
        email: "test@example.com",
        password: "wrong-password",
      }),
    ).rejects.toEqual(error);
  });
});

describe("createGuest", () => {
  it("creates a guest account and returns the user data and tokens", async () => {
    mockFetchResponse(authResponse, true, 201);

    const result = await createGuest();

    expect(fetch).toHaveBeenCalledWith(
      apiUrl("/api/auth/guest/"),
      {
        method: "POST",
      },
    );

    expect(result).toEqual(authResponse);
  });

  it("throws the error returned by the backend when guest creation fails", async () => {
    const error = {
      detail: "Guest account creation failed.",
    };

    mockFetchResponse(error, false, 500);

    await expect(createGuest()).rejects.toEqual(error);
  });
});