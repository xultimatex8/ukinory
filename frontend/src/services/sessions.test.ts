
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { wsUrl } from "../api";
import { ApiError } from "./api";
import {
  buildSocketUrl,
  classifyFatalError,
  type FatalSessionError,
  type Invite,
  type ParticipantState,
  type SessionStatus,
} from "./sessions";

vi.mock("../api", () => ({
  wsUrl: vi.fn((path: string) => `ws://localhost${path}`),
}));

const mockedWsUrl = vi.mocked(wsUrl);

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("classifyFatalError", () => {
  it("returns not_found for a 404 ApiError", () => {
    expect(classifyFatalError(new ApiError(404, "Session not found"))).toBe(
      "not_found",
    );
  });

  it("returns forbidden for a 403 ApiError", () => {
    expect(classifyFatalError(new ApiError(403, "Access forbidden"))).toBe(
      "forbidden",
    );
  });

  it("returns closed for a 410 ApiError", () => {
    expect(classifyFatalError(new ApiError(410, "Session closed"))).toBe(
      "closed",
    );
  });

  it.each([400, 401, 422, 429, 500, 503])(
    "returns null for a non-fatal HTTP status %i",
    (status) => {
      expect(classifyFatalError(new ApiError(status, "Request failed"))).toBe(
        null,
      );
    },
  );

  it("returns null for a regular Error", () => {
    expect(classifyFatalError(new Error("Something went wrong"))).toBeNull();
  });

  it("returns null for a string", () => {
    expect(classifyFatalError("Session not found")).toBeNull();
  });

  it("returns null for null and undefined", () => {
    expect(classifyFatalError(null)).toBeNull();
    expect(classifyFatalError(undefined)).toBeNull();
  });

  it("returns null for a plain object with a status property", () => {
    expect(classifyFatalError({ status: 404, message: "Not found" })).toBeNull();
  });

  it("returns null for an ApiError subclass with an unrecognized status", () => {
    class CustomApiError extends ApiError {}

    expect(classifyFatalError(new CustomApiError(418, "Unexpected status"))).toBeNull();
  });
});

describe("buildSocketUrl", () => {
  it("builds a WebSocket URL with the token query parameter", () => {
    mockedWsUrl.mockReturnValue("ws://localhost/ws/sessions/session-123/");

    const result = buildSocketUrl("/ws/sessions/session-123/", "token-abc");

    expect(mockedWsUrl).toHaveBeenCalledWith(
      "/ws/sessions/session-123/",
    );

    const url = new URL(result);
    expect(url.protocol).toBe("ws:");
    expect(url.pathname).toBe("/ws/sessions/session-123/");
    expect(url.searchParams.get("token")).toBe("token-abc");
  });

  it("encodes special characters in the token", () => {
    mockedWsUrl.mockReturnValue("wss://example.com/ws/sessions/room/");

    const token = "token with spaces&symbols?";

    const result = buildSocketUrl("/ws/sessions/room/", token);
    const url = new URL(result);

    expect(url.searchParams.get("token")).toBe(token);
    expect(result).toContain("token=token+with+spaces%26symbols%3F");
  });

  it("preserves existing query parameters and adds the token", () => {
    mockedWsUrl.mockReturnValue(
      "wss://example.com/ws/sessions/room/?mode=live",
    );

    const result = buildSocketUrl("/ws/sessions/room/?mode=live", "abc123");
    const url = new URL(result);

    expect(url.searchParams.get("mode")).toBe("live");
    expect(url.searchParams.get("token")).toBe("abc123");
  });

  it("replaces an existing token query parameter", () => {
    mockedWsUrl.mockReturnValue(
      "wss://example.com/ws/sessions/room/?token=old&mode=live",
    );

    const result = buildSocketUrl(
      "/ws/sessions/room/?token=old&mode=live",
      "new-token",
    );
    const url = new URL(result);

    expect(url.searchParams.getAll("token")).toEqual(["new-token"]);
    expect(url.searchParams.get("mode")).toBe("live");
  });

  it("propagates errors when wsUrl returns an invalid URL", () => {
    mockedWsUrl.mockReturnValue("not a valid URL");

    expect(() => buildSocketUrl("/ws/invalid/", "token")).toThrow();
  });
});

describe("session types", () => {
  it("supports the declared session status values", () => {
    const statuses: SessionStatus[] = ["WAITING", "ACTIVE", "FINISHED"];

    expect(statuses).toEqual(["WAITING", "ACTIVE", "FINISHED"]);
  });

  it("supports the declared fatal session error values", () => {
    const errors: FatalSessionError[] = [
      "not_found",
      "forbidden",
      "closed",
    ];

    expect(errors).toEqual(["not_found", "forbidden", "closed"]);
  });

  it("allows valid invite and participant state objects", () => {
    const invite: Invite = {
      code: "invite-123",
      expires_at: "2026-12-31T23:59:59Z",
    };

    const participant: ParticipantState = {
      id: "session-123",
      status: "WAITING",
      participants: 1,
      partner_joined: false,
      you_have_data: true,
      partner_has_data: null,
    };

    expect(invite.code).toBe("invite-123");
    expect(participant.status).toBe("WAITING");
  });
});