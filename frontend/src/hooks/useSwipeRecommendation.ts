import { useCallback, useEffect, useState } from "react";
import type { MotionValue } from "motion/react";

import {
  getSwipeRecommendation,
  type MovieRecommendation,
} from "../services/swipeSessions";
import { getErrorMessage } from "../utils/errors";

interface UseSwipeRecommendationParams {
  id: string | undefined;
  dragX: MotionValue<number>;
  dragRotate: MotionValue<number>;
  cardOpacity: MotionValue<number>;
  backCardY: MotionValue<number>;
  cardStackGap: number;
}

interface UseSwipeRecommendationResult {
  movie: MovieRecommendation | null;
  candidateId: string | null;
  isLoading: boolean;
  finished: boolean;
  error: string | null;
  loadRecommendation: () => Promise<void>;
  setMovie: React.Dispatch<React.SetStateAction<MovieRecommendation | null>>;
  setCandidateId: React.Dispatch<React.SetStateAction<string | null>>;
  setFinished: React.Dispatch<React.SetStateAction<boolean>>;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  setIsLoading: React.Dispatch<React.SetStateAction<boolean>>;
}

export function useSwipeRecommendation({
  id,
  dragX,
  dragRotate,
  cardOpacity,
  backCardY,
  cardStackGap,
}: UseSwipeRecommendationParams): UseSwipeRecommendationResult {
  const [movie, setMovie] = useState<MovieRecommendation | null>(null);
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resetCardAnimation = useCallback(() => {
    dragX.set(0);
    dragRotate.set(0);
    cardOpacity.set(1);
    backCardY.set(cardStackGap);
  }, [dragX, dragRotate, cardOpacity, backCardY, cardStackGap]);

  const loadRecommendation = useCallback(async () => {
    if (!id) {
      setError("Swipe session ID is missing.");
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      setFinished(false);

      const result = await getSwipeRecommendation(id);

      if (result.finished || !result.movie || !result.candidate_id) {
        setFinished(true);
        setMovie(null);
        setCandidateId(null);
        return;
      }

      setMovie(result.movie);
      setCandidateId(result.candidate_id);
      resetCardAnimation();
    } catch (err) {
      setMovie(null);
      setCandidateId(null);
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [id, resetCardAnimation]);

  useEffect(() => {
    let cancelled = false;

    const loadInitialRecommendation = async () => {
      if (!id) {
        setError("Swipe session ID is missing.");
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        const result = await getSwipeRecommendation(id);

        if (cancelled) return;

        if (result.finished || !result.movie || !result.candidate_id) {
          setFinished(true);
          setMovie(null);
          setCandidateId(null);
          return;
        }

        setFinished(false);
        setMovie(result.movie);
        setCandidateId(result.candidate_id);
        resetCardAnimation();
      } catch (err) {
        if (cancelled) return;

        setMovie(null);
        setCandidateId(null);
        setError(getErrorMessage(err));
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadInitialRecommendation();

    return () => {
      cancelled = true;
    };
  }, [id, resetCardAnimation]);

  return {
    movie,
    candidateId,
    isLoading,
    finished,
    error,
    loadRecommendation,
    setMovie,
    setCandidateId,
    setFinished,
    setError,
    setIsLoading,
  };
}
