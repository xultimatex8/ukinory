import { useCallback } from "react";
import { animate } from "motion/react";
import type { MotionValue } from "motion/react";

import { ApiError } from "../services/api";
import {
  getSwipeRecommendation,
  recordSwipe,
  type MovieRecommendation,
} from "../services/swipeSessions";
import { getErrorMessage } from "../utils/errors";

type SwipeDirection = "left" | "right";

interface UseSwipeActionsParams {
  id: string | undefined;
  movie: MovieRecommendation | null;
  candidateId: string | null;
  isSwiping: boolean;
  isRecordingSwipe: boolean;
  isPromotingBackCard: boolean;
  dragX: MotionValue<number>;
  dragRotate: MotionValue<number>;
  cardOpacity: MotionValue<number>;
  backCardY: MotionValue<number>;
  cardStackGap: number;
  promotionDuration: number;
  setMovie: React.Dispatch<React.SetStateAction<MovieRecommendation | null>>;
  setCandidateId: React.Dispatch<React.SetStateAction<string | null>>;
  setIsLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setIsPromotingBackCard: React.Dispatch<React.SetStateAction<boolean>>;
  setIsRecordingSwipe: React.Dispatch<React.SetStateAction<boolean>>;
  setIsSwiping: React.Dispatch<React.SetStateAction<boolean>>;
  setSwipeDirection: React.Dispatch<
    React.SetStateAction<SwipeDirection | null>
  >;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  setFinished: React.Dispatch<React.SetStateAction<boolean>>;
  setShowInfo: React.Dispatch<React.SetStateAction<boolean>>;
}

export function useSwipeActions({
  id,
  movie,
  candidateId,
  isSwiping,
  isRecordingSwipe,
  isPromotingBackCard,
  dragX,
  dragRotate,
  cardOpacity,
  backCardY,
  cardStackGap,
  promotionDuration,
  setMovie,
  setCandidateId,
  setIsLoading,
  setIsPromotingBackCard,
  setIsRecordingSwipe,
  setIsSwiping,
  setSwipeDirection,
  setError,
  setFinished,
  setShowInfo,
}: UseSwipeActionsParams) {
  const handleSwipe = useCallback(
    async (direction: SwipeDirection) => {
      if (
        !id ||
        !movie ||
        !candidateId ||
        isSwiping ||
        isRecordingSwipe ||
        isPromotingBackCard
      ) {
        return;
      }

      setShowInfo(false);
      setSwipeDirection(direction);
      setIsSwiping(true);
      setIsRecordingSwipe(true);
      setError(null);

      const currentMovie = movie;
      const currentCandidateId = candidateId;
      const action = direction === "right" ? "WATCHLIST" : "SKIP";
      const targetX = direction === "left" ? -800 : 800;
      const targetRotation = direction === "left" ? -18 : 18;

      try {
        await Promise.all([
          animate(dragX, targetX, {
            type: "spring",
            stiffness: 300,
            damping: 25,
          }),
          animate(dragRotate, targetRotation, {
            type: "spring",
            stiffness: 300,
            damping: 25,
          }),
          animate(cardOpacity, 0, {
            duration: 0.2,
          }),
        ]);

        await recordSwipe(id, currentCandidateId, action);

        setSwipeDirection(null);
        setIsSwiping(false);
        setIsPromotingBackCard(true);

        backCardY.set(cardStackGap);

        const recommendationPromise = getSwipeRecommendation(id);

        await animate(backCardY, 0, {
          duration: promotionDuration,
          ease: [0.22, 1, 0.36, 1],
        });

        const result = await recommendationPromise;

        if (result.finished || !result.movie || !result.candidate_id) {
          setFinished(true);
          setMovie(null);
          setCandidateId(null);
          setIsLoading(false);
          setIsPromotingBackCard(false);
          setIsRecordingSwipe(false);
          return;
        }

        setFinished(false);
        setMovie(result.movie);
        setCandidateId(result.candidate_id);
        setShowInfo(false);

        backCardY.set(0);
        dragX.set(0);
        dragRotate.set(0);
        cardOpacity.set(1);

        setIsLoading(false);
        setIsRecordingSwipe(false);
      } catch (err) {
        setSwipeDirection(null);
        setIsSwiping(false);
        setIsRecordingSwipe(false);
        setIsPromotingBackCard(false);
        setIsLoading(false);

        setMovie(currentMovie);
        setCandidateId(currentCandidateId);

        if (err instanceof ApiError) {
          setMovie(null);
          setCandidateId(null);
        }

        setError(getErrorMessage(err));

        dragX.set(0);
        dragRotate.set(0);
        cardOpacity.set(1);
        backCardY.set(cardStackGap);
      }
    },
    [
      id,
      movie,
      candidateId,
      isSwiping,
      isRecordingSwipe,
      isPromotingBackCard,
      dragX,
      dragRotate,
      cardOpacity,
      backCardY,
      cardStackGap,
      promotionDuration,
      setMovie,
      setCandidateId,
      setIsLoading,
      setIsPromotingBackCard,
      setIsRecordingSwipe,
      setIsSwiping,
      setSwipeDirection,
      setError,
      setFinished,
      setShowInfo,
    ],
  );

  const handlePromotionComplete = useCallback(() => {
    backCardY.set(cardStackGap);
    setIsPromotingBackCard(false);
  }, [backCardY, cardStackGap, setIsPromotingBackCard]);

  return {
    handleSwipe,
    handlePromotionComplete,
  };
}
