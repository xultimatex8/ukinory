import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "./api";
import { buildSocketUrl } from "./sessions";
import {
  addRecommendationToWatchlist,
  buildRoomSocketUrl,
  createComparisonRoom,
  exportRecommendationsWatchlist,
  generateComparison,
  getComparisonResult,
  getRoom,
  leaveRoom,
  regenerateInvite,
  removeRecommendationFromWatchlist,
} from "./comparisons";

vi.mock("./api", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("./sessions", () => ({
  buildSocketUrl: vi.fn(),
}));

const mockedApiFetch = vi.mocked(apiFetch);
const mockedBuildSocketUrl = vi.mocked(buildSocketUrl);

const roomState = {
  id: "room-123",
  participants: [],
  comparison_id: "comparison-123",
  generation_status: "ready",
};

const invite = {
  code: "invite-123",
  url: "https://example.com/invite/invite-123",
};

const comparisonResult = {
  id: "comparison-123",
  generated_at: "2026-01-01T12:00:00Z",
  metrics: {
    compatibility_score: 0.8,
    taste_similarity: 0.75,
    library_sizes: { user1: 20, user2: 18 },
    common_count: 5,
    overlap_ratio: 0.25,
    jaccard: 0.2,
    mean_rating_gap: 0.5,
    rating_correlation: 0.9,
    agreements: [],
    divergences: [],
  },
  narrative: "You have similar movie tastes.",
  current_user_id: "user1",
  narrative_available: true,
  recommendations: [],
};

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

describe("createComparisonRoom", () => {
  it("creates a comparison room and returns the response JSON", async () => {
    const data = { room: roomState, invite };
    mockedApiFetch.mockResolvedValue(mockJsonResponse(data));

    await expect(createComparisonRoom()).resolves.toEqual(data);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/comparison-rooms/",
      { method: "POST" },
    );
  });
});

describe("getRoom", () => {
  it("fetches a room by ID", async () => {
    mockedApiFetch.mockResolvedValue(mockJsonResponse(roomState));

    await expect(getRoom("room-123")).resolves.toEqual(roomState);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/comparison-rooms/room-123/",
      { method: "GET" },
    );
  });
});

describe("regenerateInvite", () => {
  it("regenerates and returns a room invite", async () => {
    mockedApiFetch.mockResolvedValue(mockJsonResponse(invite));

    await expect(regenerateInvite("room-123")).resolves.toEqual(invite);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/comparison-rooms/room-123/invite/",
      { method: "POST" },
    );
  });
});

describe("leaveRoom", () => {
  it("sends a DELETE request to leave the room", async () => {
    mockedApiFetch.mockResolvedValue({} as Response);

    await expect(leaveRoom("room-123")).resolves.toBeUndefined();

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/comparison-rooms/room-123/leave/",
      { method: "DELETE" },
    );
  });
});

describe("generateComparison", () => {
  it("starts comparison generation and returns the room state", async () => {
    mockedApiFetch.mockResolvedValue(mockJsonResponse(roomState));

    await expect(generateComparison("room-123")).resolves.toEqual(roomState);

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/room-123/generate/",
      { method: "POST" },
    );
  });
});

describe("getComparisonResult", () => {
  it("fetches the comparison result", async () => {
    mockedApiFetch.mockResolvedValue(mockJsonResponse(comparisonResult));

    await expect(getComparisonResult("room-123")).resolves.toEqual(
      comparisonResult,
    );

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/room-123/result/",
      { method: "GET" },
    );
  });
});

describe("addRecommendationToWatchlist", () => {
  it("adds a numeric movie ID to the watchlist", async () => {
    mockedApiFetch.mockResolvedValue({} as Response);

    await expect(
      addRecommendationToWatchlist("room-123", 42),
    ).resolves.toBeUndefined();

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/room-123/watchlist/42/",
      { method: "POST" },
    );
  });

  it("supports string movie IDs", async () => {
    mockedApiFetch.mockResolvedValue({} as Response);

    await addRecommendationToWatchlist("room-123", "movie-42");

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/room-123/watchlist/movie-42/",
      { method: "POST" },
    );
  });
});

describe("removeRecommendationFromWatchlist", () => {
  it("removes a recommendation from the watchlist", async () => {
    mockedApiFetch.mockResolvedValue({} as Response);

    await expect(
      removeRecommendationFromWatchlist("room-123", 42),
    ).resolves.toBeUndefined();

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/room-123/watchlist/42/",
      { method: "DELETE" },
    );
  });
});

describe("exportRecommendationsWatchlist", () => {
  it("fetches and returns the exported watchlist Blob", async () => {
    const blob = new Blob(["movie_id,title\n42,Example"], {
      type: "text/csv",
    });
    mockedApiFetch.mockResolvedValue(mockBlobResponse(blob));

    await expect(exportRecommendationsWatchlist("room-123")).resolves.toBe(
      blob,
    );

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/api/comparisons/room-123/watchlist/export/",
      { method: "GET" },
    );
  });
});

describe("buildRoomSocketUrl", () => {
  it("builds the WebSocket URL with the room ID and token", () => {
    mockedBuildSocketUrl.mockReturnValue(
      "wss://example.com/ws/comparison-rooms/room-123/?token=test-token",
    );

    const result = buildRoomSocketUrl("room-123", "test-token");

    expect(result).toBe(
      "wss://example.com/ws/comparison-rooms/room-123/?token=test-token",
    );
    expect(mockedBuildSocketUrl).toHaveBeenCalledWith(
      "/ws/comparison-rooms/room-123/",
      "test-token",
    );
  });
});