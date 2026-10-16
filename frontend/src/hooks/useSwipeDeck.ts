
import { useCallback, useEffect, useRef, useState } from "react";
import { animate, useMotionValue } from "motion/react";

import { ApiError } from "../services/api";
import {
  getSwipeRecommendation,
  recordSwipe,
  type MovieRecommendation,
  type RecommendationResponse,
} from "../services/swipeSessions";
import { getErrorMessage } from "../utils/errors";

export const CARD_STACK_GAP = 24;

const PROMOTION_DURATION = 0.45;
const SPRING = { type: "spring", stiffness: 300, damping: 25 } as const;

export type SwipeDirection = "left" | "right";

export function useSwipeDeck(sessionId: string | undefined) {
  const [movie, setMovie] = useState<MovieRecommendation | null>(null);
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [finished, setFinished] = useState(false);
  const [sessionNotFound, setSessionNotFound] = useState(false);
  const [sessionFinished, setSessionFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [isSwiping, setIsSwiping] = useState(false);
  const [isRecordingSwipe, setIsRecordingSwipe] = useState(false);
  const [isPromotingBackCard, setIsPromotingBackCard] = useState(false);
  const [swipeDirection, setSwipeDirection] = useState<SwipeDirection | null>(
    null,
  );

  const dragX = useMotionValue(0);
  const dragRotate = useMotionValue(0);
  const cardOpacity = useMotionValue(1);
  const backCardY = useMotionValue(CARD_STACK_GAP);

  const requestRef = useRef(0);

  const resetCardAnimation = useCallback(() => {
    dragX.set(0);
    dragRotate.set(0);
    cardOpacity.set(1);
    backCardY.set(CARD_STACK_GAP);
  }, [dragX, dragRotate, cardOpacity, backCardY]);

  const applyRecommendation = useCallback(
    (result: RecommendationResponse): boolean => {
      if (result.finished || !result.movie || !result.candidate_id) {
        setFinished(true);
        setMovie(null);
        setCandidateId(null);
        return false;
      }

      setFinished(false);
      setMovie(result.movie);
      setCandidateId(result.candidate_id);
      return true;
    },
    [],
  );

  const applyError = useCallback((err: unknown) => {
    setMovie(null);
    setCandidateId(null);

    if (err instanceof ApiError && err.status === 404) {
      setSessionNotFound(true);
      return;
    }

    if (err instanceof ApiError && err.status === 409) {
      setSessionFinished(true);
      return;
    }

    setError(getErrorMessage(err));
  }, []);

  const load = useCallback(async () => {
    if (!sessionId) {
      setError("Swipe session ID is missing.");
      setIsLoading(false);
      return;
    }

    const request = ++requestRef.current;

    setIsLoading(true);
    setError(null);
    setSessionNotFound(false);
    setSessionFinished(false);

    try {
      const result = await getSwipeRecommendation(sessionId);

      if (request !== requestRef.current) return;

      if (applyRecommendation(result)) {
        resetCardAnimation();
      }
    } catch (err) {
      if (request !== requestRef.current) return;

      applyError(err);
    } finally {
      if (request === requestRef.current) {
        setIsLoading(false);
      }
    }
  }, [sessionId, applyRecommendation, applyError, resetCardAnimation]);

  const invalidateRequests = useCallback(() => {
    requestRef.current += 1;
  }, []);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      void load();
    }, 0);

    return () => {
      clearTimeout(timeoutId);
      invalidateRequests();
    };
  }, [load, invalidateRequests]);

  const swipe = useCallback(
    async (direction: SwipeDirection) => {
      if (
        !sessionId ||
        !movie ||
        !candidateId ||
        isSwiping ||
        isRecordingSwipe ||
        isPromotingBackCard
      ) {
        return;
      }

      setSwipeDirection(direction);
      setIsSwiping(true);
      setIsRecordingSwipe(true);
      setError(null);

      const action = direction === "right" ? "WATCHLIST" : "SKIP";
      const targetX = direction === "left" ? -800 : 800;
      const targetRotation = direction === "left" ? -18 : 18;

      try {
        await Promise.all([
          animate(dragX, targetX, SPRING),
          animate(dragRotate, targetRotation, SPRING),
          animate(cardOpacity, 0, { duration: 0.2 }),
        ]);

        await recordSwipe(sessionId, candidateId, action);

        setSwipeDirection(null);
        setIsSwiping(false);
        setIsPromotingBackCard(true);

        backCardY.set(CARD_STACK_GAP);

        const nextRecommendation = getSwipeRecommendation(sessionId);
        nextRecommendation.catch(() => undefined);

        await animate(backCardY, 0, {
          duration: PROMOTION_DURATION,
          ease: [0.22, 1, 0.36, 1],
        });

        const result = await nextRecommendation;

        if (!applyRecommendation(result)) {
          setIsPromotingBackCard(false);
          setIsRecordingSwipe(false);
          return;
        }

        backCardY.set(0);
        dragX.set(0);
        dragRotate.set(0);
        cardOpacity.set(1);

        setIsRecordingSwipe(false);
      } catch (err) {
        setSwipeDirection(null);
        setIsSwiping(false);
        setIsRecordingSwipe(false);
        setIsPromotingBackCard(false);

        applyError(err);

        resetCardAnimation();
      }
    },
    [
      sessionId,
      movie,
      candidateId,
      isSwiping,
      isRecordingSwipe,
      isPromotingBackCard,
      dragX,
      dragRotate,
      cardOpacity,
      backCardY,
      applyRecommendation,
      applyError,
      resetCardAnimation,
    ],
  );

  const completePromotion = useCallback(() => {
    backCardY.set(CARD_STACK_GAP);
    setIsPromotingBackCard(false);
  }, [backCardY]);

  const locked =
    isLoading ||
    isSwiping ||
    isRecordingSwipe ||
    isPromotingBackCard ||
    !movie ||
    !candidateId;

  return {
    movie,
    candidateId,
    isLoading,
    finished,
    sessionNotFound,
    sessionFinished,
    error,
    isPromotingBackCard,
    swipeDirection,
    locked,
    dragX,
    dragRotate,
    cardOpacity,
    backCardY,
    swipe,
    completePromotion,
    retry: load,
  };
}
