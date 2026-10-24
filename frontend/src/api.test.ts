import { afterEach, describe, expect, it, vi } from "vitest";

async function loadApiModule(prod: boolean, apiBaseUrl: string) {
  vi.resetModules();
  vi.stubEnv("PROD", prod);
  vi.stubEnv("VITE_API_URL", apiBaseUrl);

  return import("./api");
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("apiUrl", () => {
  it("returns the original input in development", async () => {
    const { apiUrl } = await loadApiModule(false, "");

    expect(apiUrl("/api/users/")).toBe("/api/users/");
    expect(apiUrl(new URL("https://example.com/data"))).toEqual(
      new URL("https://example.com/data"),
    );
  });

  it("returns the original input for non-backend paths in production", async () => {
    const { apiUrl } = await loadApiModule(
      true,
      "https://api.example.com",
    );

    expect(apiUrl("/assets/logo.svg")).toBe("/assets/logo.svg");
  });

  it("prefixes API paths with the configured backend URL in production", async () => {
    const { apiUrl } = await loadApiModule(
      true,
      "https://api.example.com",
    );

    expect(apiUrl("/api/users/")).toBe(
      "https://api.example.com/api/users/",
    );
  });

  it("prefixes health paths with the configured backend URL in production", async () => {
    const { apiUrl } = await loadApiModule(
      true,
      "https://api.example.com",
    );

    expect(apiUrl("/health")).toBe("https://api.example.com/health");
  });

  it("throws when the API URL is missing for backend paths in production", async () => {
    const { apiUrl } = await loadApiModule(true, "");

    expect(() => apiUrl("/api/users/")).toThrow(
      "VITE_API_URL is not configured.",
    );
  });

  it("does not prefix non-string inputs in production", async () => {
    const { apiUrl } = await loadApiModule(
      true,
      "https://api.example.com",
    );
    const input = new URL("https://example.com/data");

    expect(apiUrl(input)).toBe(input);
  });
});

describe("wsUrl", () => {
  it("uses the current origin in development and converts HTTP to WS", async () => {
    const { wsUrl } = await loadApiModule(false, "");

    expect(wsUrl("/ws/notifications/")).toBe(
      `${window.location.origin.replace(/^http/, "ws")}/ws/notifications/`,
    );
  });

  it("converts HTTPS backend URLs to WSS in production", async () => {
    const { wsUrl } = await loadApiModule(
      true,
      "https://api.example.com",
    );

    expect(wsUrl("/ws/notifications/")).toBe(
      "wss://api.example.com/ws/notifications/",
    );
  });

  it("converts HTTP backend URLs to WS in production", async () => {
    const { wsUrl } = await loadApiModule(
      true,
      "http://localhost:8000",
    );

    expect(wsUrl("/ws/notifications/")).toBe(
      "ws://localhost:8000/ws/notifications/",
    );
  });

  it("throws when the API URL is missing in production", async () => {
    const { wsUrl } = await loadApiModule(true, "");

    expect(() => wsUrl("/ws/notifications/")).toThrow(
      "VITE_API_URL is not configured.",
    );
  });
});