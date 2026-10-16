import { useState } from "react";
import { LogOut } from "lucide-react";
import { useParams } from "react-router-dom";
import AppLogo from "../../../../components/AppLogo";
import EndSessionModal from "../../../../components/EndSessionModal";
import ErrorScreen from "../../../../components/ErrorScreen";
import MovieInfoModal from "../../../../components/MovieInfoModal";
import MovieInformation from "../../../../components/MovieInformation";
import PairedSessionOverlay from "../../../../components/PairedSessionOverlay";
import RateMovieModal from "../../../../components/RateMovieModal";
import { getStreamingCountries } from "../../../../components/StreamingProviders";
import SwipeActionBar from "../../../../components/SwipeActionBar";
import SwipeInstructions from "../../../../components/SwipeInstructions";
import SwipeMovieCard from "../../../../components/SwipeMovieCard";
import { useEndSwipeSession } from "../../../../hooks/useEndSwipeSession";
import { useHeartbeat } from "../../../../hooks/useHeartbeat";
import type { PairedSessionController } from "../../../../hooks/usePairedSession";
import { useSwipeDeck } from "../../../../hooks/useSwipeDeck";

interface DiscoverSessionScreenProps {
  paired?: PairedSessionController;
}

export default function DiscoverSessionScreen({
  paired,
}: DiscoverSessionScreenProps) {
  const { id } = useParams<{ id: string }>();

  const [infoCandidateId, setInfoCandidateId] = useState<string | null>(null);
  const [showEndSessionModal, setShowEndSessionModal] = useState(false);
  const [showRateModal, setShowRateModal] = useState(false);

  const deck = useSwipeDeck(id);
  const { movie, candidateId } = deck;

  useHeartbeat(id, !deck.finished && !deck.error);

  const {
    isEndingSession,
    endSessionError,
    clearEndSessionError,
    handleGoHome,
    handleDownloadCsv,
  } = useEndSwipeSession({ id });

  // Tied to the current candidate, so it closes by itself when the card changes.
  const showInfo = infoCandidateId !== null && infoCandidateId === candidateId;

  const handleOpenEndSessionModal = () => {
    clearEndSessionError();
    setShowEndSessionModal(true);
  };

  const handleCloseEndSessionModal = () => {
    if (isEndingSession) return;

    clearEndSessionError();
    setShowEndSessionModal(false);
  };

  const handleMovieRated = () => {
    setShowRateModal(false);
    void deck.swipe("left");
  };

  const streamingCountries = getStreamingCountries(movie);

  const endSessionModal = showEndSessionModal && (
    <EndSessionModal
      isEndingSession={isEndingSession}
      error={endSessionError}
      onClose={handleCloseEndSessionModal}
      onGoHome={handleGoHome}
      onDownloadCsv={handleDownloadCsv}
    />
  );

  const pairedOverlay =
    paired && id ? <PairedSessionOverlay sessionId={id} paired={paired} /> : null;

  if (deck.sessionNotFound) {
    return (
      <ErrorScreen
        message="This swipe session does not exist or is no longer available."
        buttonText="Back to home"
      />
    );
  }

  const endedByPartner =
    Boolean(paired) && (Boolean(paired?.ended) || deck.sessionFinished);

  if (deck.sessionFinished && !paired) {
    return (
      <ErrorScreen
        message="This swipe session has already finished."
        buttonText="Back to home"
      />
    );
  }

  if (deck.error && !endedByPartner) {
    return <ErrorScreen message={deck.error} onRetry={deck.retry} />;
  }

  if (deck.finished || endedByPartner) {
    return (
      <main className="min-h-screen bg-background text-text">
        <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
          <h2 className="text-2xl font-bold">
            {endedByPartner ? "Session ended" : "No more recommendations"}
          </h2>

          <p className="mt-3 max-w-md text-sm leading-relaxed text-text-muted">
            {endedByPartner
              ? "This session is over. You can still download your watchlist."
              : "You've gone through all the movies currently available."}
          </p>

          <button
            type="button"
            onClick={handleOpenEndSessionModal}
            className="mt-6 flex cursor-pointer items-center justify-center gap-2 border border-primary px-5 py-2.5 text-sm font-medium text-primary transition hover:bg-primary hover:text-background"
          >
            <LogOut size={15} />
            {endedByPartner ? "Get my watchlist" : "End session"}
          </button>
        </div>

        {endSessionModal}
        {pairedOverlay}
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
                      locked={deck.locked}
                      isPromotingBackCard={deck.isPromotingBackCard}
                      swipeDirection={deck.swipeDirection}
                      dragX={deck.dragX}
                      dragRotate={deck.dragRotate}
                      cardOpacity={deck.cardOpacity}
                      backCardY={deck.backCardY}
                      onSwipe={deck.swipe}
                      onShowInfo={() => setInfoCandidateId(candidateId)}
                      onPromotionComplete={deck.completePromotion}
                    />
                  ) : (
                    deck.isLoading && (
                      <div className="absolute inset-0 z-20 flex items-center justify-center rounded-xl border border-border bg-surface">
                        <span className="text-8xl font-light leading-none text-text-muted">
                          ?
                        </span>
                      </div>
                    )
                  )}
                </div>

                <div className="mt-6 flex flex-col items-center sm:mt-7">
                  <SwipeActionBar
                    disabled={deck.locked}
                    onSkip={() => void deck.swipe("left")}
                    onWatched={() => setShowRateModal(true)}
                    onWatchlist={() => void deck.swipe("right")}
                  />

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

      {pairedOverlay}

      {showInfo && movie && (
        <MovieInfoModal
          movie={movie}
          streamingCountries={streamingCountries}
          onClose={() => setInfoCandidateId(null)}
        />
      )}

      {endSessionModal}

      {showRateModal && movie && (
        <RateMovieModal
          movieId={movie.tmdb_id}
          movieTitle={movie.title}
          onClose={() => setShowRateModal(false)}
          onSaved={handleMovieRated}
        />
      )}
    </main>
  );
}