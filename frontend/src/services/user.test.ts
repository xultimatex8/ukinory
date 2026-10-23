import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "./api";
import {
  getCurrentUser,
  updateUser,
  changePassword,
  claimGuest,
  signOut,
  deleteAccount,
  exportUserData,
} from "./user";
import type { User, AuthResponse } from "./user";

vi.mock("./api", () => ({
  apiFetch: vi.fn(),
}));

const mockApiFetch = vi.mocked(apiFetch);

const user: User = {
  id: 1,
  email: "test@example.com",
  username: "testuser",
  is_guest: false,
};

const authResponse: AuthResponse = {
  user,
  access: "access-token",
  refresh: "refresh-token",
};

function mockJsonResponse(body: unknown) {
  mockApiFetch.mockResolvedValue({
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response);
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("getCurrentUser", () => {
  it("fetches and returns the current user", async () => {
    mockJsonResponse(user);

    await expect(getCurrentUser()).resolves.toEqual(user);

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/auth/me/",
      { method: "GET" },
    );
  });
});

describe("updateUser", () => {
  it("sends the updated user data", async () => {
    const data = {
      email: "updated@example.com",
      username: "updateduser",
    };

    mockJsonResponse({ ...user, ...data });

    await expect(updateUser(data)).resolves.toEqual({
      ...user,
      ...data,
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/auth/me/",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
    );
  });
});

describe("changePassword", () => {
  it("sends the password fields using the API naming convention", async () => {
    mockApiFetch.mockResolvedValue({} as Response);

    await changePassword({
      oldPassword: "OldPassword123!",
      newPassword: "NewPassword123!",
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/auth/me/password/",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          old_password: "OldPassword123!",
          new_password: "NewPassword123!",
        }),
      },
    );
  });
});

describe("claimGuest", () => {
  it("sends the guest claim data and returns the authentication response", async () => {
    const data = {
      email: "test@example.com",
      username: "testuser",
      password: "Password123!",
      accepted_documents: ["terms"],
    };

    mockJsonResponse(authResponse);

    await expect(claimGuest(data)).resolves.toEqual(authResponse);

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/auth/guest/claim/",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
    );
  });
});

describe("signOut", () => {
  it("clears local tokens without making a request when no refresh token exists", async () => {
    localStorage.setItem("access_token", "access-token");

    await signOut();

    expect(mockApiFetch).not.toHaveBeenCalled();
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("sends the refresh token and clears tokens after the request", async () => {
    localStorage.setItem("access_token", "access-token");
    localStorage.setItem("refresh_token", "refresh-token");
    mockApiFetch.mockResolvedValue({} as Response);

    await signOut();

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/auth/logout/",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: "refresh-token" }),
      },
    );

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("clears tokens even if the logout request fails", async () => {
    localStorage.setItem("access_token", "access-token");
    localStorage.setItem("refresh_token", "refresh-token");
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    await expect(signOut()).rejects.toThrow("Network error");

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });
});

describe("deleteAccount", () => {
  it("sends an empty object when no password is provided", async () => {
    mockApiFetch.mockResolvedValue({} as Response);

    await deleteAccount();

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/auth/me/delete/",
      {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      },
    );
  });

  it("sends the password when provided", async () => {
    mockApiFetch.mockResolvedValue({} as Response);

    await deleteAccount("Password123!");

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/auth/me/delete/",
      {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: "Password123!" }),
      },
    );
  });
});

describe("exportUserData", () => {
  it("downloads the exported account data as a JSON file", async () => {
    const blob = new Blob(['{"email":"test@example.com"}'], {
      type: "application/json",
    });

    mockApiFetch.mockResolvedValue({
      blob: vi.fn().mockResolvedValue(blob),
    } as unknown as Response);

    const click = vi.fn();
    const remove = vi.fn();

    vi.spyOn(document, "createElement").mockReturnValue({
      href: "",
      download: "",
      click,
      remove,
    } as unknown as HTMLAnchorElement);

    const appendChild = vi
      .spyOn(document.body, "appendChild")
      .mockImplementation((node) => node);

    const createObjectURL = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:test-url");

    const revokeObjectURL = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => {});

    await exportUserData();

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/auth/me/export/",
      { method: "GET" },
    );
    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(click).toHaveBeenCalledOnce();
    expect(remove).toHaveBeenCalledOnce();
    expect(appendChild).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test-url");
  });
});