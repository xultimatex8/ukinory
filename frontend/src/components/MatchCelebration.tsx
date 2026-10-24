import { useEffect } from "react";
import { Heart } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { MatchToast } from "../hooks/usePairedSession";

const AUTO_DISMISS_SECONDS = 7;
const PARTICLE_COUNT = 28;
const PARTICLE_COLORS = [
  "bg-primary",
  "bg-yellow-300",
  "bg-red-400",
  "bg-emerald-400",
  "bg-sky-400",
  "bg-text",
];

function seeded(index: number, salt: number): number {
  const x = Math.sin(index * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

const PARTICLES = Array.from({ length: PARTICLE_COUNT }, (_, i) => {
  const angle = (i / PARTICLE_COUNT) * Math.PI * 2 + seeded(i, 1) * 0.4;
  const distance = 150 + seeded(i, 2) * 170;

  return {
    id: i,
    x: Math.cos(angle) * distance,
    y: Math.sin(angle) * distance,
    rotate: seeded(i, 3) * 540 - 270,
    size: 6 + Math.round(seeded(i, 4) * 6),
    delay: seeded(i, 5) * 0.12,
    color: PARTICLE_COLORS[i % PARTICLE_COLORS.length],
  };
});

interface MatchCelebrationProps {
  match: MatchToast | null;
  onDismiss: () => void;
  onViewMatches: () => void;
}

export default function MatchCelebration({
  match,
  onDismiss,
  onViewMatches,
}: MatchCelebrationProps) {
  useEffect(() => {
    if (!match) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onDismiss();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [match, onDismiss]);

  return (
    <AnimatePresence>
      {match && (
        <motion.button
          key={match.candidateId}
          role="dialog"
          aria-modal="true"
          aria-label="New match"
          className="fixed inset-0 z-60 flex items-center justify-center bg-background/90 p-6 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          onClick={onDismiss}
        >
          <button
            className="flex w-full max-w-sm flex-col items-center text-center"
            onClick={(event) => event.stopPropagation()}
          >
            <motion.div
              className="flex items-center gap-2 border border-primary bg-surface px-4 py-2 text-xs font-bold uppercase tracking-widest text-primary"
              initial={{ y: -16, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.1, duration: 0.3 }}
            >
              <motion.span
                animate={{ scale: [1, 1.3, 1] }}
                transition={{ duration: 0.9, repeat: Infinity }}
                className="flex"
              >
                <Heart size={14} fill="currentColor" />
              </motion.span>
              It&apos;s a match!
            </motion.div>

            <div className="relative mt-6">
              <motion.div
                aria-hidden
                className="absolute -inset-4 bg-primary/30 blur-2xl"
                animate={{ opacity: [0.4, 0.9, 0.4] }}
                transition={{ duration: 2.2, repeat: Infinity }}
              />

              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 flex items-center justify-center"
              >
                {PARTICLES.map((particle) => (
                  <motion.span
                    key={particle.id}
                    className={`absolute ${particle.color}`}
                    style={{ width: particle.size, height: particle.size }}
                    initial={{ x: 0, y: 0, scale: 0, opacity: 1 }}
                    animate={{
                      x: particle.x,
                      y: particle.y,
                      scale: [0, 1, 1],
                      opacity: [1, 1, 0],
                      rotate: particle.rotate,
                    }}
                    transition={{
                      duration: 1.4,
                      delay: particle.delay,
                      ease: "easeOut",
                    }}
                  />
                ))}
              </div>

              <motion.div
                className="relative h-72 w-48 border border-border bg-surface shadow-2xl"
                initial={{ scale: 0.6, rotate: -8, opacity: 0 }}
                animate={{ scale: 1, rotate: 0, opacity: 1 }}
                transition={{
                  type: "spring",
                  stiffness: 220,
                  damping: 16,
                  delay: 0.05,
                }}
              >
                {match.posterUrl ? (
                  <motion.img
                    key={match.posterUrl}
                    src={match.posterUrl}
                    alt={`${match.title} poster`}
                    className="h-full w-full object-cover"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.3 }}
                  />
                ) : (
                  <div className="flex h-full w-full animate-pulse items-center justify-center bg-background text-text-muted">
                    <Heart size={32} />
                  </div>
                )}
              </motion.div>
            </div>

            <motion.div
              className="mt-6"
              initial={{ y: 12, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.3 }}
            >
              <p className="text-xs uppercase tracking-widest text-text-muted">
                You both want to watch
              </p>
              <h2 className="mt-2 text-2xl font-bold text-text">{match.title}</h2>
              {match.releaseYear && (
                <p className="mt-1 text-sm text-text-muted">
                  {match.releaseYear}
                </p>
              )}
            </motion.div>

            <motion.div
              className="mt-8 flex w-full flex-col gap-3 sm:flex-row"
              initial={{ y: 12, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.4, duration: 0.3 }}
            >
              <button
                type="button"
                onClick={onDismiss}
                className="flex-1 border border-border bg-surface px-4 py-3 text-sm font-semibold text-text-secondary transition-colors hover:border-primary hover:text-primary cursor-pointer"
              >
                Keep swiping
              </button>
              <button
                type="button"
                onClick={onViewMatches}
                className="flex-1 border border-primary bg-primary px-4 py-3 text-sm font-semibold text-background transition-opacity hover:opacity-90 cursor-pointer"
              >
                See all matches
              </button>
            </motion.div>
          </button>

          <motion.div
            aria-hidden
            className="absolute inset-x-0 bottom-0 h-1 origin-left bg-primary"
            initial={{ scaleX: 1 }}
            animate={{ scaleX: 0 }}
            transition={{ duration: AUTO_DISMISS_SECONDS, ease: "linear" }}
            onAnimationComplete={onDismiss}
          />
        </motion.button>
      )}
    </AnimatePresence>
  );
}