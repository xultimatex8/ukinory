
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "./api";
import {
  acceptInvite,
  INVITE_TYPES,
  inviteTargetPath,
  type AcceptInviteResponse,
} from "./invites";

vi.mock("./api", () => ({
  apiFetch: vi.fn(),
}));

const mockedApiFetch = vi.mocked(apiFetch);

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("INVITE_TYPES", () => {
  it("exposes the supported invite types", () => {
    expect(INVITE_TYPES).toEqual({
      COMPARISON: "COMPARISON",
      PAIRED_SWIPE: "PAIRED_SWIPE",
    });
  });
});

describe("inviteTargetPath", () => {
  it("returns the comparison room path for a comparison invite", () => {
    const response: AcceptInviteResponse = {
      invite: { code: "invite-123", type: "COMPARISON" },
      target: { id: "room-123", type: "COMPARISON" },
    };

    expect(inviteTargetPath(response)).toBe("/comparison/room/room-123");
  });

  it("returns the paired swipe path for a paired swipe invite", () => {
    const response: AcceptInviteResponse = {
      invite: { code: "invite-456", type: "PAIRED_SWIPE" },
      target: { id: "session-456", type: "PAIRED_SWIPE" },
    };

    expect(inviteTargetPath(response)).toBe("/discover/together/session-456");
  });

  it("supports an invite without a code", () => {
    const response: AcceptInviteResponse = {
      invite: { type: "COMPARISON" },
      target: { id: "room-789", type: "COMPARISON" },
    };

    expect(inviteTargetPath(response)).toBe("/comparison/room/room-789");
  });

  it("throws an error for an unsupported invite type", () => {
    const response = {
      invite: { type: "UNKNOWN" },
      target: { id: "target-123", type: "UNKNOWN" },
    } as AcceptInviteResponse;

    expect(() => inviteTargetPath(response)).toThrow(
      "Unsupported invite type: UNKNOWN",
    );
  });
});

describe("acceptInvite", () => {
  it("accepts an invite and returns the response JSON", async () => {
    const data: AcceptInviteResponse = {
      invite: { code: "invite-123", type: "COMPARISON" },
      target: { id: "room-123", type: "COMPARISON" },
    };

    mockedApiFetch.mockResolvedValue({
      json: vi.fn().mockResolvedValue(data),
    } as unknown as Response);

    await expect(acceptInvite("invite-123")).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/invites/invite-123/accept/",
      { method: "POST" },
    );
    expect(mockedApiFetch).toHaveBeenCalledTimes(1);
  });

  it("URL-encodes the invite code before sending the request", async () => {
    const data: AcceptInviteResponse = {
      invite: { code: "invite /?&", type: "PAIRED_SWIPE" },
      target: { id: "session-123", type: "PAIRED_SWIPE" },
    };

    mockedApiFetch.mockResolvedValue({
      json: vi.fn().mockResolvedValue(data),
    } as unknown as Response);

    await expect(acceptInvite("invite /?&")).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      `/api/invites/${encodeURIComponent("invite /?&")}/accept/`,
      { method: "POST" },
    );
  });

  it("propagates errors from apiFetch", async () => {
    const error = new Error("Request failed");
    mockedApiFetch.mockRejectedValue(error);

    await expect(acceptInvite("invalid-code")).rejects.toBe(error);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/invites/invalid-code/accept/",
      { method: "POST" },
    );
  });

  it("propagates errors when parsing the response JSON", async () => {
    const error = new Error("Invalid JSON");

    mockedApiFetch.mockResolvedValue({
      json: vi.fn().mockRejectedValue(error),
    } as unknown as Response);

    await expect(acceptInvite("invite-123")).rejects.toBe(error);
  });
});