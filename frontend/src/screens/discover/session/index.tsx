import { useState } from "react";
import { useMotionValue } from "motion/react";
import { Check, Heart, LogOut, X } from "lucide-react";
import { useLocation, useParams } from "react-router-dom";

import EndSessionModal from "../../../components/EndSessionModal";
import ErrorScreen from "../../../components/ErrorScreen";
import MovieInfoModal from "../../../components/MovieInfoModal";
import MovieInformation from "../../../components/MovieInformation";
import RateMovieModal from "../../../components/RateMovieModal";
import { getStreamingCountries } from "../../../components/StreamingProviders";
import SwipeInstructions from "../../../components/SwipeInstructions";
import SwipeMovieCard from "../../../components/SwipeMovieCard";
import { useEndSwipeSession } from "../../../hooks/useEndSwipeSession";
import { useSwipeActions } from "../../../hooks/useSwipeActions";
import { useSwipeRecommendation } from "../../../hooks/useSwipeRecommendation";
import { useSwipeSessionLifecycle } from "../../../hooks/useSwipeSessionLifecycle";
import AppLogo from "../../../components/AppLogo";

type SwipeDirection = "left" | "right" | null;

const CARD_STACK_GAP = 24;
const PROMOTION_DURATION = 0.45;

export default function DiscoverSessionScreen() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();

  const [leaveToken, setLeaveToken] = useState<string | null>(
    (location.state as { leaveToken?: string } | null)?.leaveToken ?? null,
  );

  const [isPromotingBackCard, setIsPromotingBackCard] = useState(false);
  const [isSwiping, setIsSwiping] = useState(false);
  const [isRecordingSwipe, setIsRecordingSwipe] = useState(false);
  const [swipeDirection, setSwipeDirection] =
    useState<SwipeDirection>(null);
  const [showInfo, setShowInfo] = useState(false);
  const [showEndSessionModal, setShowEndSessionModal] = useState(false);
  const [showRateModal, setShowRateModal] = useState(false);

  const dragX = useMotionValue(0);
  const dragRotate = useMotionValue(0);
  const cardOpacity = useMotionValue(1);
  const backCardY = useMotionValue(CARD_STACK_GAP);

  const {
    movie,
    candidateId,
    isLoading,
    finished,
    sessionNotFound,
    sessionFinished,
    error,
    loadRecommendation,
    setMovie,
    setCandidateId,
    setFinished,
    setError,
    setIsLoading,
  } = useSwipeRecommendation({
    id,
    dragX,
    dragRotate,
    cardOpacity,
    backCardY,
    cardStackGap: CARD_STACK_GAP,
  });

  useSwipeSessionLifecycle({
    id,
    leaveToken,
    finished,
    error,
    setLeaveToken,
  });

  const {
    handleSwipe,
    handlePromotionComplete,
  } = useSwipeActions({
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
    cardStackGap: CARD_STACK_GAP,
    promotionDuration: PROMOTION_DURATION,
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
  });

  const {
    isEndingSession,
    endSessionError,
    clearEndSessionError,
    handleGoHome,
    handleDownloadCsv,
  } = useEndSwipeSession({ id });

  const handleRetry = () => {
    void loadRecommendation();
  };

  const handleOpenEndSessionModal = () => {
    clearEndSessionError();
    setShowEndSessionModal(true);
  };

  const handleOpenRateModal = () => {
    setShowRateModal(true);
  };

  const handleCloseRateModal = () => {
    setShowRateModal(false);
  };

  const handleMovieRated = () => {
    setShowRateModal(false);
    void handleSwipe("left");
  };

  const handleCloseEndSessionModal = () => {
    if (isEndingSession) return;

    clearEndSessionError();
    setShowEndSessionModal(false);
  };

  const streamingCountries = getStreamingCountries(movie);

  if (sessionNotFound) {
    return (
      <ErrorScreen
        message="This swipe session does not exist or is no longer available."
        buttonText="Back to home"
      />
    );
  }

  if (sessionFinished) {
    return (
      <ErrorScreen
        message="This swipe session has already finished."
        buttonText="Back to home"
      />
    );
  }

  if (error) {
    return (
      <ErrorScreen
        message={error}
        onRetry={handleRetry}
      />
    );
  }

  if (finished) {
    return (
      <main className="min-h-screen bg-background text-text">
        <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
          <h2 className="text-2xl font-bold">
            No more recommendations
          </h2>

          <p className="mt-3 max-w-md text-sm leading-relaxed text-text-muted">
            You've gone through all the movies currently available.
          </p>

          <button
            type="button"
            onClick={handleOpenEndSessionModal}
            className="mt-6 flex cursor-pointer items-center justify-center gap-2 border border-primary px-5 py-2.5 text-sm font-medium text-primary transition hover:bg-primary hover:text-background"
          >
            <LogOut size={15} />
            End session
          </button>
        </div>

        {showEndSessionModal && (
          <EndSessionModal
            isEndingSession={isEndingSession}
            error={endSessionError}
            onClose={handleCloseEndSessionModal}
            onGoHome={handleGoHome}
            onDownloadCsv={handleDownloadCsv}
          />
        )}
      </main>
    );
  }

  return (
    <main className="min-h-screen overflow-hidden bg-background text-text">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-4 sm:px-6 sm:py-6 lg:px-8 xl:px-10">
        <div className="flex flex-1 items-start justify-center pt-6 xl:pt-1 2xl:pt-6">
          <div className="flex w-full items-center justify-center gap-8 lg:gap-14 2xl:gap-20">
            <div className="hidden xl:flex flex-col items-center">
              <div className="hidden 2xl:flex mb-8">
                <AppLogo />
              </div>

              <SwipeInstructions />
            </div>

            <div className="flex min-w-0 flex-col items-center xl:flex-1">
              <div className="mb-10 2xl:hidden">
                <AppLogo />
              </div>

              <div className="w-full max-w-90 xl:w-full xl:max-w-120">
                <div className="relative h-130 w-full xl:h-[min(calc(100vh-190px),680px)]">
                  {movie && candidateId ? (
                    <SwipeMovieCard
                      movie={movie}
                      candidateId={candidateId}
                      sessionId={id!}
                      isLoading={isLoading}
                      isSwiping={isSwiping}
                      isRecordingSwipe={isRecordingSwipe}
                      isPromotingBackCard={isPromotingBackCard}
                      swipeDirection={swipeDirection}
                      dragX={dragX}
                      dragRotate={dragRotate}
                      cardOpacity={cardOpacity}
                      backCardY={backCardY}
                      onSwipe={handleSwipe}
                      onShowInfo={() => setShowInfo(true)}
                      onPromotionComplete={handlePromotionComplete}
                    />
                  ) : (
                    isLoading && (
                      <div className="absolute inset-0 z-20 flex items-center justify-center rounded-xl border border-border bg-surface">
                        <span className="text-8xl font-light leading-none text-text-muted">
                          ?
                        </span>
                      </div>
                    )
                  )}
                </div>

                <div className="mt-6 flex flex-col items-center sm:mt-7">
                  <div className="grid w-full grid-cols-3 gap-2 sm:flex sm:items-center sm:justify-center sm:gap-4">
                    <button
                      type="button"
                      disabled={
                        isLoading ||
                        isSwiping ||
                        isRecordingSwipe ||
                        isPromotingBackCard ||
                        !movie ||
                        !candidateId
                      }
                      onClick={() => void handleSwipe("left")}
                      aria-label="Skip"
                      className="flex h-12 min-w-0 cursor-pointer items-center justify-center gap-1.5 border
                        border-red-400/30 bg-red-400/5 px-2 text-xs font-medium text-red-400 transition
                        hover:border-red-400/60 hover:bg-red-400/10 disabled:cursor-auto disabled:opacity-40
                        sm:w-28 sm:gap-2 sm:px-0 sm:text-sm"
                    >
                      <X size={18} strokeWidth={1.8} />
                      <span className="truncate">Skip</span>
                    </button>

                    <button
                      type="button"
                      disabled={
                        isLoading ||
                        isSwiping ||
                        isRecordingSwipe ||
                        isPromotingBackCard ||
                        !movie ||
                        !candidateId
                      }
                      onClick={handleOpenRateModal}
                      aria-label="Mark as watched"
                      className="flex h-12 min-w-0 cursor-pointer items-center justify-center gap-1.5 border
                        border-emerald-400/50 bg-emerald-400/5 px-2 text-xs font-medium text-emerald-400 transition
                        hover:border-emerald-400 hover:bg-emerald-400 hover:text-background disabled:cursor-auto disabled:opacity-40
                        sm:w-28 sm:gap-2 sm:px-0 sm:text-sm"
                    >
                      <Check size={16} strokeWidth={1.8} />
                      <span className="truncate">Watched</span>
                    </button>

                    <button
                      type="button"
                      disabled={
                        isLoading ||
                        isSwiping ||
                        isRecordingSwipe ||
                        isPromotingBackCard ||
                        !movie ||
                        !candidateId
                      }
                      onClick={() => void handleSwipe("right")}
                      aria-label="Add to watchlist"
                      className="flex h-12 min-w-0 cursor-pointer items-center justify-center gap-1.5 border
                        border-primary/50 bg-primary/5 px-2 text-xs font-medium text-primary transition
                        hover:border-primary hover:bg-primary hover:text-background disabled:cursor-auto disabled:opacity-40
                        sm:w-28 sm:gap-2 sm:px-0 sm:text-sm"
                    >
                      <Heart size={18} strokeWidth={1.8} />
                      <span className="truncate">Watchlist</span>
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={handleOpenEndSessionModal}
                    className="mt-5 flex cursor-pointer items-center gap-2 border border-border bg-surface px-4 py-2 text-xs font-medium text-text-muted transition hover:bg-surface-hover hover:text-text"
                  >
                    <LogOut size={14} strokeWidth={1.7} />
                    End session
                  </button>

                  <div className="mt-6 xl:hidden">
                    <SwipeInstructions />
                  </div>
                </div>
              </div>
            </div>

            <MovieInformation
              movie={movie}
              streamingCountries={streamingCountries}
            />
          </div>
        </div>
      </div>

      {showInfo && movie && (
        <MovieInfoModal
          movie={movie}
          streamingCountries={streamingCountries}
          onClose={() => setShowInfo(false)}
        />
      )}

      {showEndSessionModal && (
        <EndSessionModal
          isEndingSession={isEndingSession}
          error={endSessionError}
          onClose={handleCloseEndSessionModal}
          onGoHome={handleGoHome}
          onDownloadCsv={handleDownloadCsv}
        />
      )}

      {showRateModal && movie && (
        <RateMovieModal
          movieId={movie.tmdb_id}
          movieTitle={movie.title}
          onClose={handleCloseRateModal}
          onSaved={handleMovieRated}
        />
      )}
    </main>
  );
}
