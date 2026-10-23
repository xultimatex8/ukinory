import { useRef } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { animate, useMotionValue } from "motion/react";
import type { MotionValue } from "motion/react";
import { ApiError } from "../services/api";
import {
  getSwipeRecommendation,
  recordSwipe,
  type MovieRecommendation,
  type RecommendationResponse,
} from "../services/swipeSessions";
import { getErrorMessage } from "../utils/errors";
import { CARD_STACK_GAP, useSwipeDeck } from "./useSwipeDeck";

vi.mock("motion/react", () => ({
  animate: vi.fn(() => Promise.resolve()),
  useMotionValue: vi.fn((initialValue: number) => {
    const valueRef = useRef<{
      motionValue: MotionValue<number>;
    } | null>(null);

    if (valueRef.current === null) {
      let currentValue = initialValue;
      const set = vi.fn((nextValue: number) => {
        currentValue = nextValue;
      });
      const motionValue = {
        get: () => currentValue,
        set,
      } as unknown as MotionValue<number>;

      valueRef.current = { motionValue };
    }

    return valueRef.current.motionValue;
  }),
}));

vi.mock("../services/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  },
}));

vi.mock("../services/swipeSessions", () => ({
  getSwipeRecommendation: vi.fn(),
  recordSwipe: vi.fn(),
}));

vi.mock("../utils/errors", () => ({
  getErrorMessage: vi.fn(),
}));

const mockedAnimate = vi.mocked(animate);
const mockedUseMotionValue = vi.mocked(useMotionValue);
const mockedGetSwipeRecommendation = vi.mocked(getSwipeRecommendation);
const mockedRecordSwipe = vi.mocked(recordSwipe);
const mockedGetErrorMessage = vi.mocked(getErrorMessage);

function makeMovie(
  overrides: Partial<MovieRecommendation> = {},
): MovieRecommendation {
  return {
    tmdb_id: 123,
    title: "Example Movie",
    release_year: 2024,
    synopsis: "An example synopsis",
    poster_url: "https://example.com/poster.jpg",
    vote_average: 7.5,
    runtime: 120,
    streaming_providers: {},
    genres: [],
    ...overrides,
  };
}

function makeRecommendation(
  overrides: Partial<RecommendationResponse> = {},
): RecommendationResponse {
  return {
    finished: false,
    candidate_id: "candidate-1",
    movie: makeMovie(),
    ...overrides,
  };
}

function makeApiError(message: string, status: number): Error {
  const MockedApiError = ApiError as unknown as new (
    message: string,
    status: number,
  ) => Error;

  return new MockedApiError(message, status);
}

describe("useSwipeDeck", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    mockedGetSwipeRecommendation.mockResolvedValue(makeRecommendation());
    mockedRecordSwipe.mockResolvedValue({ matched: false, match: null });
    mockedGetErrorMessage.mockReturnValue("Something went wrong");
    mockedAnimate.mockImplementation(() => Promise.resolve() as never);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads the initial recommendation", async () => {
    const { result } = renderHook(() => useSwipeDeck("session-1"));

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(mockedGetSwipeRecommendation).toHaveBeenCalledWith("session-1");
      expect(result.current.movie?.title).toBe("Example Movie");
    });

    expect(result.current.candidateId).toBe("candidate-1");
    expect(result.current.isLoading).toBe(false);
    expect(result.current.finished).toBe(false);
    expect(result.current.locked).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("sets an error when the session ID is missing", async () => {
    const { result } = renderHook(() => useSwipeDeck(undefined));

    await waitFor(() => {
      expect(result.current.error).toBe("Swipe session ID is missing.");
    });

    expect(result.current.isLoading).toBe(false);
    expect(mockedGetSwipeRecommendation).not.toHaveBeenCalled();
  });

  it("marks the deck as finished when no recommendation is available", async () => {
    mockedGetSwipeRecommendation.mockResolvedValueOnce(
      makeRecommendation({ finished: true, candidate_id: null, movie: null }),
    );

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() => {
      expect(result.current.finished).toBe(true);
    });

    expect(result.current.movie).toBeNull();
    expect(result.current.candidateId).toBeNull();
    expect(result.current.locked).toBe(true);
  });

  it("treats a missing movie as a finished deck", async () => {
    mockedGetSwipeRecommendation.mockResolvedValueOnce(
      makeRecommendation({ movie: null }),
    );

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() => {
      expect(result.current.finished).toBe(true);
    });
  });

  it("handles a 404 response by marking the session as not found", async () => {
    mockedGetSwipeRecommendation.mockRejectedValueOnce(
      makeApiError("Not found", 404),
    );

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() => {
      expect(result.current.sessionNotFound).toBe(true);
    });

    expect(result.current.movie).toBeNull();
    expect(result.current.candidateId).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("handles a 409 response by marking the session as finished", async () => {
    mockedGetSwipeRecommendation.mockRejectedValueOnce(
      makeApiError("Session finished", 409),
    );

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() => {
      expect(result.current.sessionFinished).toBe(true);
    });

    expect(result.current.error).toBeNull();
  });

  it("uses the error message utility for unexpected load failures", async () => {
    const failure = new Error("Network failure");
    mockedGetSwipeRecommendation.mockRejectedValueOnce(failure);

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() => {
      expect(result.current.error).toBe("Something went wrong");
    });

    expect(mockedGetErrorMessage).toHaveBeenCalledWith(failure);
  });

  it("resets session error flags when retrying", async () => {
    mockedGetSwipeRecommendation
      .mockRejectedValueOnce(makeApiError("Not found", 404))
      .mockResolvedValueOnce(
        makeRecommendation({ candidate_id: "candidate-2" }),
      );

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() => expect(result.current.sessionNotFound).toBe(true));

    await act(async () => {
      await result.current.retry();
    });

    expect(result.current.sessionNotFound).toBe(false);
    expect(result.current.sessionFinished).toBe(false);
    expect(result.current.candidateId).toBe("candidate-2");
    expect(result.current.error).toBeNull();
  });

  it("ignores stale recommendation responses", async () => {
    let resolveFirst!: (value: RecommendationResponse) => void;

    const firstRequest = new Promise<RecommendationResponse>((resolve) => {
      resolveFirst = resolve;
    });

    mockedGetSwipeRecommendation.mockReturnValueOnce(firstRequest);

    const { result, rerender } = renderHook(
      ({ sessionId }: { sessionId: string | undefined }) =>
        useSwipeDeck(sessionId),
      { initialProps: { sessionId: "session-1" } },
    );

    await waitFor(() =>
      expect(mockedGetSwipeRecommendation).toHaveBeenCalledTimes(1),
    );

    rerender({ sessionId: "session-2" });

    await waitFor(() => {
      expect(mockedGetSwipeRecommendation).toHaveBeenCalledWith("session-2");
      expect(result.current.candidateId).toBe("candidate-1");
    });

    await act(async () => {
      resolveFirst(makeRecommendation({ candidate_id: "stale-candidate" }));
      await firstRequest;
    });

    expect(result.current.candidateId).toBe("candidate-1");
  });

  it("records a right swipe as WATCHLIST and loads the next recommendation", async () => {
    mockedGetSwipeRecommendation
      .mockResolvedValueOnce(makeRecommendation())
      .mockResolvedValueOnce(
        makeRecommendation({
          candidate_id: "candidate-2",
          movie: makeMovie({ title: "Next Movie" }),
        }),
      );

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() =>
      expect(result.current.candidateId).toBe("candidate-1"),
    );

    await act(async () => {
      await result.current.swipe("right");
    });

    expect(mockedRecordSwipe).toHaveBeenCalledWith(
      "session-1",
      "candidate-1",
      "WATCHLIST",
    );
    expect(result.current.candidateId).toBe("candidate-2");
    expect(result.current.movie?.title).toBe("Next Movie");

    expect(result.current.isPromotingBackCard).toBe(true);
    expect(result.current.locked).toBe(true);

    act(() => {
      result.current.completePromotion();
    });

    expect(result.current.isPromotingBackCard).toBe(false);
    expect(result.current.locked).toBe(false);
  });

  it("records a left swipe as SKIP", async () => {
    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() =>
      expect(result.current.candidateId).toBe("candidate-1"),
    );

    await act(async () => {
      await result.current.swipe("left");
    });

    expect(mockedRecordSwipe).toHaveBeenCalledWith(
      "session-1",
      "candidate-1",
      "SKIP",
    );

    expect(result.current.isPromotingBackCard).toBe(true);
  });

  it("locks swiping while the promotion animation is active", async () => {
    let finishAnimation!: () => void;

    mockedAnimate.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finishAnimation = resolve;
        }) as never,
    );

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() =>
      expect(result.current.candidateId).toBe("candidate-1"),
    );

    let swipePromise!: Promise<void>;

    act(() => {
      swipePromise = result.current.swipe("right");
    });

    expect(result.current.locked).toBe(true);

    await act(async () => {
      finishAnimation();
      await swipePromise;
    });
  });

  it("does not swipe when there is no active recommendation", async () => {
    mockedGetSwipeRecommendation.mockResolvedValueOnce(
      makeRecommendation({ finished: true, candidate_id: null, movie: null }),
    );

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() => expect(result.current.finished).toBe(true));

    await act(async () => {
      await result.current.swipe("right");
    });

    expect(mockedRecordSwipe).not.toHaveBeenCalled();
  });

  it("handles swipe failures and resets card animation values", async () => {
    const failure = new Error("Swipe failed");
    mockedRecordSwipe.mockRejectedValueOnce(failure);

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() =>
      expect(result.current.candidateId).toBe("candidate-1"),
    );

    await act(async () => {
      await result.current.swipe("left");
    });

    expect(mockedGetErrorMessage).toHaveBeenCalledWith(failure);
    expect(result.current.error).toBe("Something went wrong");
    expect(result.current.swipeDirection).toBeNull();
    expect(result.current.isPromotingBackCard).toBe(false);

    expect(result.current.movie).toBeNull();
    expect(result.current.candidateId).toBeNull();
    expect(result.current.locked).toBe(true);

    const motionValues = mockedUseMotionValue.mock.results.map(
      (entry) => entry.value as { get: () => number },
    );

    expect(motionValues[0].get()).toBe(0);
    expect(motionValues[1].get()).toBe(0);
    expect(motionValues[2].get()).toBe(1);
    expect(motionValues[3].get()).toBe(CARD_STACK_GAP);
  });

  it("ends the deck when the next recommendation is finished", async () => {
    mockedGetSwipeRecommendation
      .mockResolvedValueOnce(makeRecommendation())
      .mockResolvedValueOnce(
        makeRecommendation({
          finished: true,
          candidate_id: null,
          movie: null,
        }),
      );

    const { result } = renderHook(() => useSwipeDeck("session-1"));

    await waitFor(() =>
      expect(result.current.candidateId).toBe("candidate-1"),
    );

    await act(async () => {
      await result.current.swipe("left");
    });

    expect(result.current.finished).toBe(true);
    expect(result.current.movie).toBeNull();
    expect(result.current.candidateId).toBeNull();
    expect(result.current.isPromotingBackCard).toBe(false);
    expect(result.current.locked).toBe(true);
  });

  it("resets the back-card position when promotion completes", async () => {
    const { result } = renderHook(() => useSwipeDeck("session-1"));

    act(() => {
      result.current.completePromotion();
    });

    const backCardValue = mockedUseMotionValue.mock.results[3]?.value as {
      set: ReturnType<typeof vi.fn>;
    };

    expect(backCardValue.set).toHaveBeenCalledWith(CARD_STACK_GAP);
    expect(result.current.isPromotingBackCard).toBe(false);
  });

  it("exposes the expected initial animation values and state", () => {
    const { result } = renderHook(() => useSwipeDeck("session-1"));

    expect(result.current.dragX).toBeDefined();
    expect(result.current.dragRotate).toBeDefined();
    expect(result.current.cardOpacity).toBeDefined();
    expect(result.current.backCardY).toBeDefined();
    expect(result.current.swipeDirection).toBeNull();
    expect(result.current.isPromotingBackCard).toBe(false);
  });
});