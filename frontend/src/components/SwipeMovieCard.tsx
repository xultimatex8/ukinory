import {
  animate,
  motion,
  type MotionValue,
  type PanInfo,
} from "motion/react";
import { Info, Star } from "lucide-react";
import type { MovieRecommendation } from "../services/swipeSessions";
import WhyRecommended from "./WhyRecommend";

interface SwipeMovieCardProps {
  movie: MovieRecommendation;
  candidateId: string;
  sessionId: string;
  isLoading: boolean;
  isSwiping: boolean;
  isRecordingSwipe: boolean;
  isPromotingBackCard: boolean;
  swipeDirection: "left" | "right" | null;

  dragX: MotionValue<number>;
  dragRotate: MotionValue<number>;
  cardOpacity: MotionValue<number>;
  backCardY: MotionValue<number>;

  onSwipe: (direction: "left" | "right") => void;
  onShowInfo: () => void;
  onPromotionComplete: () => void;
}

const SWIPE_THRESHOLD = 120;
const MAX_DRAG_ROTATION = 12;

const CARD_STACK_GAP = 24;
const MOVIE_FADE_DURATION = 0.3;

export default function SwipeMovieCard({
  movie,
  candidateId,
  sessionId,
  isLoading,
  isSwiping,
  isRecordingSwipe,
  isPromotingBackCard,
  swipeDirection,
  dragX,
  dragRotate,
  cardOpacity,
  backCardY,
  onSwipe,
  onShowInfo,
  onPromotionComplete,
}: SwipeMovieCardProps) {
  const handleDrag = () => {
    if (
      isSwiping ||
      isRecordingSwipe ||
      isPromotingBackCard ||
      isLoading
    ) {
      return;
    }

    const x = dragX.get();

    const rotation = Math.max(
      -MAX_DRAG_ROTATION,
      Math.min(
        MAX_DRAG_ROTATION,
        (x / 300) * MAX_DRAG_ROTATION,
      ),
    );

    dragRotate.set(rotation);
  };

  const handleDragEnd = (
    _event: MouseEvent | TouchEvent | PointerEvent,
    info: PanInfo,
  ) => {
    if (
      isSwiping ||
      isRecordingSwipe ||
      isPromotingBackCard ||
      isLoading
    ) {
      return;
    }

    const offsetX = info.offset.x;

    if (offsetX > SWIPE_THRESHOLD) {
      onSwipe("right");
      return;
    }

    if (offsetX < -SWIPE_THRESHOLD) {
      onSwipe("left");
      return;
    }

    animate(dragX, 0, {
      type: "spring",
      stiffness: 300,
      damping: 25,
    });

    animate(dragRotate, 0, {
      type: "spring",
      stiffness: 300,
      damping: 25,
    });
  };

  return (
    <>
      {isPromotingBackCard && (
        <div
          className="absolute inset-x-0 top-0 z-0 overflow-hidden rounded-xl border border-border bg-surface"
          style={{
            height: `calc(100% - ${CARD_STACK_GAP}px)`,
            transform: `translateY(${CARD_STACK_GAP}px)`,
          }}
        >
          <div className="flex h-full items-center justify-center">
            <span className="text-8xl font-light leading-none text-border">
              ?
            </span>
          </div>
        </div>
      )}

      <motion.div
        className="absolute inset-x-0 top-0 z-10 overflow-hidden rounded-xl border border-border bg-surface shadow-xl"
        style={{
          y: backCardY,
          height: `calc(100% - ${CARD_STACK_GAP}px)`,
        }}
      >
        <div className="flex h-full items-center justify-center">
          <span className="text-8xl font-light leading-none text-border">
            ?
          </span>
        </div>

        {isPromotingBackCard && (
          <button
            type="button"
            disabled
            aria-label="More information"
            className="absolute right-4 top-4 z-20 flex h-10 w-10 items-center justify-center rounded-full border border-white/30 bg-black/50 text-white backdrop-blur-sm disabled:cursor-not-allowed disabled:opacity-100 sm:right-5 sm:top-5 sm:h-11 sm:w-11 lg:hidden"
          >
            <Info size={20} />
          </button>
        )}
      </motion.div>

      <motion.div
        key={candidateId}
        drag={
          isSwiping ||
          isRecordingSwipe ||
          isLoading ||
          isPromotingBackCard
            ? false
            : "x"
        }
        dragConstraints={{
          left: 0,
          right: 0,
        }}
        dragElastic={0.8}
        onDrag={handleDrag}
        onDragEnd={handleDragEnd}
        initial={{
          opacity: isPromotingBackCard ? 0 : 1,
        }}
        animate={{
          opacity: 1,
        }}
        transition={{
          duration: MOVIE_FADE_DURATION,
          ease: "easeInOut",
        }}
        onAnimationComplete={() => {
          if (isPromotingBackCard) {
            onPromotionComplete();
          }
        }}
        className="absolute inset-x-0 top-0 z-20 touch-pan-y cursor-grab active:cursor-grabbing"
        style={{
          x: dragX,
          rotate: dragRotate,
          opacity: cardOpacity,
          height: `calc(100% - ${CARD_STACK_GAP}px)`,
        }}
      >
        <article className="relative h-full w-full overflow-hidden rounded-xl border border-border bg-surface select-none shadow-2xl">
          {movie.poster_url ? (
            <img
              src={movie.poster_url}
              alt={`${movie.title} poster`}
              draggable={false}
              className="absolute inset-0 h-full w-full object-cover"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-background">
              <p className="text-sm text-text-muted">
                No poster available
              </p>
            </div>
          )}

          <div className="absolute inset-0 bg-linear-to-t from-black via-black/20 to-transparent" />

          <motion.div
            initial={false}
            animate={{
              opacity:
                swipeDirection === "right" ? 1 : 0,
            }}
            className="absolute left-6 top-6 border-2 border-primary px-4 py-2 text-2xl font-bold tracking-widest text-primary"
          >
            LIKE
          </motion.div>

          <motion.div
            initial={false}
            animate={{
              opacity:
                swipeDirection === "left" ? 1 : 0,
            }}
            className="absolute right-6 top-6 border-2 border-red-400 px-4 py-2 text-2xl font-bold tracking-widest text-red-400"
          >
            NOPE
          </motion.div>

          <button
            type="button"
            disabled={
              isSwiping ||
              isRecordingSwipe ||
              isLoading ||
              isPromotingBackCard
            }
            onPointerDown={(event) =>
              event.stopPropagation()
            }
            onClick={(event) => {
              event.stopPropagation();
              onShowInfo();
            }}
            aria-label="More information"
            className="absolute right-4 top-4 z-20 flex h-10 w-10 items-center justify-center rounded-full border border-white/30 bg-black/50 text-white backdrop-blur-sm transition hover:border-white hover:bg-black/70 disabled:cursor-not-allowed disabled:opacity-50 sm:right-5 sm:top-5 sm:h-11 sm:w-11 lg:hidden"
          >
            <Info size={20} />
          </button>

          <div className="absolute inset-x-0 bottom-0 p-5 sm:p-6">
            <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              {movie.title}
            </h2>

            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-white/75">
              {movie.release_year && (
                <span>{movie.release_year}</span>
              )}

              {movie.runtime && (
                <span>
                  {Math.floor(movie.runtime / 60)}h{" "}
                  {movie.runtime % 60} min
                </span>
              )}

              {movie.vote_average !== null && (
                <span className="inline-flex items-center gap-1">
                  <Star
                    size={14}
                    fill="currentColor"
                  />
                  {movie.vote_average.toFixed(1)}
                </span>
              )}
            </div>

            {movie.genres.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {movie.genres.map((genre) => (
                  <span
                    key={genre.tmdb_id}
                    className="border border-white/20 bg-black/30 px-2 py-1 text-xs text-white/80"
                  >
                    {genre.name}
                  </span>
                ))}
              </div>
            )}

            <WhyRecommended
              sessionId={sessionId}
              candidateId={candidateId}
            />
          </div>
        </article>
      </motion.div>
    </>
  );
}