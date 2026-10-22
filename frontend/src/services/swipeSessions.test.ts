
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "./api";
import { buildSocketUrl } from "./sessions";
import {
  buildSessionSocketUrl,
  createIndividualSwipeSession,
  createPairedSwipeSession,
  endSwipeSession,
  getPairedSessionState,
  getRecommendationJustification,
  getSessionMatches,
  getSwipeRecommendation,
  getSwipeSession,
  recordSwipe,
  regeneratePairedInvite,
  sendHeartbeat,
  startSwipeSession,
} from "./swipeSessions";

vi.mock("./api", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("./sessions", () => ({
  buildSocketUrl: vi.fn(),
}));

const mockedApiFetch = vi.mocked(apiFetch);
const mockedBuildSocketUrl = vi.mocked(buildSocketUrl);

function mockJsonResponse(data: unknown): Response {
  return {
    json: vi.fn().mockResolvedValue(data),
  } as unknown as Response;
}

function mockBlobResponse(blob: Blob): Response {
  return {
    blob: vi.fn().mockResolvedValue(blob),
  } as unknown as Response;
}

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("createIndividualSwipeSession", () => {
  it("creates an individual swipe session", async () => {
    const data = { id: "session-1", type: "INDIVIDUAL", status: "WAITING" };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(createIndividualSwipeSession()).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith("/api/swipe-sessions/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "INDIVIDUAL" }),
    });
  });

  it("propagates API errors", async () => {
    const error = new Error("Request failed");
    mockedApiFetch.mockRejectedValue(error);

    await expect(createIndividualSwipeSession()).rejects.toBe(error);
  });
});

describe("startSwipeSession", () => {
  it("starts a session", async () => {
    const data = { id: "session-1", type: "INDIVIDUAL", status: "ACTIVE" };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(startSwipeSession("session-1")).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/session-1/start/",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      },
    );
  });
});

describe("getSwipeRecommendation", () => {
  it("returns the next movie recommendation", async () => {
    const data = {
      finished: false,
      candidate_id: "candidate-1",
      movie: {
        tmdb_id: 550,
        title: "Fight Club",
        release_year: 1999,
        synopsis: "An office worker forms an underground fight club.",
        poster_url: "/poster.jpg",
        vote_average: 8.8,
        runtime: 139,
        streaming_providers: {},
        genres: [{ tmdb_id: 18, name: "Drama" }],
      },
    };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(getSwipeRecommendation("session-1")).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/session-1/recommendation/",
      { method: "GET" },
    );
  });

  it("returns a finished response when there are no more recommendations", async () => {
    const data = { finished: true, candidate_id: null, movie: null };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(getSwipeRecommendation("session-1")).resolves.toEqual(data);
  });
});

describe("getRecommendationJustification", () => {
  it("requests and returns a recommendation justification", async () => {
    const data = { justification: "Matches your favorite genres.", available: true };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(
      getRecommendationJustification("session-1", "candidate-1"),
    ).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/session-1/candidates/candidate-1/justification/",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  it("supports unavailable justifications", async () => {
    const data = { justification: null, available: false };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(
      getRecommendationJustification("session-1", "candidate-1"),
    ).resolves.toEqual(data);
  });
});

describe("recordSwipe", () => {
  it.each(["SKIP", "WATCHLIST"] as const)(
    "records a %s action",
    async (action) => {
      const data = {
        matched: false,
        match: null,
      };
      mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

      await expect(
        recordSwipe("session-1", "candidate-1", action),
      ).resolves.toEqual(data);

      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/swipe-sessions/session-1/swipe/",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            candidate_id: "candidate-1",
            action,
          }),
        },
      );
    },
  );

  it("returns match details when a swipe creates a match", async () => {
    const data = {
      matched: true,
      match: {
        candidate_id: "candidate-1",
        movie_id: "movie-1",
        tmdb_id: 550,
        title: "Fight Club",
        release_year: 1999,
      },
    };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(
      recordSwipe("session-1", "candidate-1", "WATCHLIST"),
    ).resolves.toEqual(data);
  });
});

describe("endSwipeSession", () => {
  it("ends the session and returns the response blob", async () => {
    const blob = new Blob(["session results"], { type: "text/csv" });
    mockedApiFetch.mockResolvedValue(mockBlobResponse(blob));

    await expect(endSwipeSession("session-1")).resolves.toBe(blob);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/session-1/end/",
      { method: "POST" },
    );
  });

  it("propagates errors from apiFetch", async () => {
    const error = new Error("Unable to end session");
    mockedApiFetch.mockRejectedValue(error);

    await expect(endSwipeSession("session-1")).rejects.toBe(error);
  });
});

describe("getSwipeSession", () => {
  it("returns the session details", async () => {
    const data = { id: "session-1", type: "INDIVIDUAL", status: "ACTIVE" };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(getSwipeSession("session-1")).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/session-1/",
      { method: "GET" },
    );
  });
});

describe("sendHeartbeat", () => {
  it("sends a heartbeat for the session", async () => {
    mockedApiFetch.mockResolvedValue({} as Response);

    await expect(sendHeartbeat("session-1")).resolves.toBeUndefined();

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/session-1/heartbeat/",
      { method: "POST" },
    );
  });

  it("swallows API errors so the next heartbeat can retry", async () => {
    mockedApiFetch.mockRejectedValue(new Error("Network unavailable"));

    await expect(sendHeartbeat("session-1")).resolves.toBeUndefined();

    expect(mockedApiFetch).toHaveBeenCalledTimes(1);
  });
});

describe("createPairedSwipeSession", () => {
  it("creates a paired swipe session", async () => {
    const data = {
      session: {
        id: "paired-1",
        status: "WAITING",
        participants: 1,
        partner_joined: false,
        you_have_data: true,
        partner_has_data: null,
        type: "PAIRED_SWIPE",
        current_user_id: "user-1",
        matches_count: 0,
      },
      invite: {
        code: "invite-1",
        expires_at: "2026-12-31T23:59:59Z",
      },
    };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(createPairedSwipeSession()).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/paired/",
      { method: "POST" },
    );
  });
});

describe("getPairedSessionState", () => {
  it("returns the paired session state", async () => {
    const data = {
      id: "paired-1",
      status: "ACTIVE",
      participants: 2,
      partner_joined: true,
      you_have_data: true,
      partner_has_data: true,
      type: "PAIRED_SWIPE",
      current_user_id: "user-1",
      matches_count: 3,
    };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(getPairedSessionState("paired-1")).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/paired-1/paired/",
      { method: "GET" },
    );
  });
});

describe("regeneratePairedInvite", () => {
  it("regenerates and returns the paired invite", async () => {
    const data = {
      code: "new-invite",
      expires_at: "2026-12-31T23:59:59Z",
    };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(regeneratePairedInvite("paired-1")).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/paired-1/invite/",
      { method: "POST" },
    );
  });
});

describe("getSessionMatches", () => {
  it("returns the session matches", async () => {
    const data = [
      {
        candidate_id: "candidate-1",
        matched_at: "2026-01-01T12:00:00Z",
        movie: {
          tmdb_id: 550,
          title: "Fight Club",
          release_year: 1999,
          poster_url: "/poster.jpg",
        },
      },
    ];
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(getSessionMatches("paired-1")).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/swipe-sessions/paired-1/matches/",
      { method: "GET" },
    );
  });

  it("returns an empty array when there are no matches", async () => {
    mockedApiFetch.mockResolvedValue(mockJsonResponse([]));

    await expect(getSessionMatches("paired-1")).resolves.toEqual([]);
  });
});

describe("buildSessionSocketUrl", () => {
  it("builds the WebSocket URL for the specified session", () => {
    mockedBuildSocketUrl.mockReturnValue(
      "wss://example.com/ws/swipe-sessions/session-1/?token=abc",
    );

    const result = buildSessionSocketUrl("session-1", "abc");

    expect(mockedBuildSocketUrl).toHaveBeenCalledWith(
      "/ws/swipe-sessions/session-1/",
      "abc",
    );
    expect(result).toBe(
      "wss://example.com/ws/swipe-sessions/session-1/?token=abc",
    );
  });
});