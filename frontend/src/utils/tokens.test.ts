
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  hasSession,
  setTokens,
} from "./tokens";

const ACCESS_KEY = "access_token";
const REFRESH_KEY = "refresh_token";

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("getAccessToken", () => {
  it("returns the access token when it exists", () => {
    localStorage.setItem(ACCESS_KEY, "access-123");

    expect(getAccessToken()).toBe("access-123");
  });

  it("returns null when the access token does not exist", () => {
    expect(getAccessToken()).toBeNull();
  });
});

describe("getRefreshToken", () => {
  it("returns the refresh token when it exists", () => {
    localStorage.setItem(REFRESH_KEY, "refresh-123");

    expect(getRefreshToken()).toBe("refresh-123");
  });

  it("returns null when the refresh token does not exist", () => {
    expect(getRefreshToken()).toBeNull();
  });
});

describe("hasSession", () => {
  it("returns true when both tokens exist", () => {
    localStorage.setItem(ACCESS_KEY, "access-123");
    localStorage.setItem(REFRESH_KEY, "refresh-123");

    expect(hasSession()).toBe(true);
  });

  it("returns false when neither token exists", () => {
    expect(hasSession()).toBe(false);
  });

  it("returns false when only the access token exists", () => {
    localStorage.setItem(ACCESS_KEY, "access-123");

    expect(hasSession()).toBe(false);
  });

  it("returns false when only the refresh token exists", () => {
    localStorage.setItem(REFRESH_KEY, "refresh-123");

    expect(hasSession()).toBe(false);
  });

  it("returns false when either token is an empty string", () => {
    localStorage.setItem(ACCESS_KEY, "access-123");
    localStorage.setItem(REFRESH_KEY, "");

    expect(hasSession()).toBe(false);
  });
});

describe("setTokens", () => {
  it("stores both access and refresh tokens", () => {
    setTokens("access-123", "refresh-123");

    expect(localStorage.getItem(ACCESS_KEY)).toBe("access-123");
    expect(localStorage.getItem(REFRESH_KEY)).toBe("refresh-123");
  });

  it("updates the access token", () => {
    setTokens("old-access", "old-refresh");

    setTokens("new-access", "new-refresh");

    expect(getAccessToken()).toBe("new-access");
    expect(getRefreshToken()).toBe("new-refresh");
  });

  it("preserves the existing refresh token when refresh is omitted", () => {
    localStorage.setItem(REFRESH_KEY, "existing-refresh");

    setTokens("new-access");

    expect(getAccessToken()).toBe("new-access");
    expect(getRefreshToken()).toBe("existing-refresh");
  });

  it("preserves the existing refresh token when refresh is null", () => {
    localStorage.setItem(REFRESH_KEY, "existing-refresh");

    setTokens("new-access", null);

    expect(getAccessToken()).toBe("new-access");
    expect(getRefreshToken()).toBe("existing-refresh");
  });

  it("preserves the existing refresh token when refresh is an empty string", () => {
    localStorage.setItem(REFRESH_KEY, "existing-refresh");

    setTokens("new-access", "");

    expect(getRefreshToken()).toBe("existing-refresh");
  });

  it("does not create a refresh token when none exists and refresh is omitted", () => {
    setTokens("access-123");

    expect(getAccessToken()).toBe("access-123");
    expect(getRefreshToken()).toBeNull();
  });
});

describe("clearTokens", () => {
  it("removes both tokens", () => {
    setTokens("access-123", "refresh-123");

    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("does not throw when no tokens exist", () => {
    expect(() => clearTokens()).not.toThrow();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("does not remove unrelated local storage values", () => {
    localStorage.setItem(ACCESS_KEY, "access-123");
    localStorage.setItem(REFRESH_KEY, "refresh-123");
    localStorage.setItem("theme", "dark");

    clearTokens();

    expect(localStorage.getItem("theme")).toBe("dark");
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });
});