import { useState } from "react";
import { Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { getRecommendationJustification } from "../services/swipeSessions";

interface WhyRecommendedProps {
  sessionId: string;
  candidateId: string;
}

export default function WhyRecommended({
  sessionId,
  candidateId,
}: WhyRecommendedProps) {
  const [showJustification, setShowJustification] = useState(false);
  const [justification, setJustification] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isAvailable, setIsAvailable] = useState(true);

  const handleToggle = async () => {
    if (isLoading) {
      return;
    }

    if (showJustification) {
      setShowJustification(false);
      return;
    }

    if (justification) {
      setShowJustification(true);
      return;
    }

    setIsLoading(true);

    try {
      const result = await getRecommendationJustification(
        sessionId,
        candidateId,
      );

      if (!result.available) {
        setIsAvailable(false);
        return;
      }

      if (result.justification) {
        setJustification(result.justification);
        setShowJustification(true);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mt-4 border-t border-white/20 pt-3">
      <button
        type="button"
        onPointerDown={(event) =>
          event.stopPropagation()
        }
        onClick={(event) => {
          event.stopPropagation();
          void handleToggle();
        }}
        disabled={isLoading}
        className="flex cursor-pointer items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary transition-colors hover:text-sky-300 disabled:cursor-auto disabled:opacity-60"
      >
        <Sparkles size={11} />
        {isLoading
          ? "Thinking..."
          : !isAvailable
            ? "Explanation unavailable"
            : showJustification
              ? "Hide explanation"
              : "Why this movie"}
      </button>

      {!isAvailable && (
        <p className="mt-1.5 text-xs leading-relaxed text-white/50">
          Explanations are currently unavailable.
        </p>
      )}

      {showJustification && (
        <div className="mt-1.5 text-xs leading-relaxed text-white/70">
          <ReactMarkdown
            components={{
              p: ({ children }) => (
                <p className="mb-2 last:mb-0">
                  {children}
                </p>
              ),
              ul: ({ children }) => (
                <ul className="mb-2 list-disc space-y-1 pl-4 last:mb-0">
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol className="mb-2 list-decimal space-y-1 pl-4 last:mb-0">
                  {children}
                </ol>
              ),
              strong: ({ children }) => (
                <strong className="font-semibold text-white/90">
                  {children}
                </strong>
              ),
              em: ({ children }) => (
                <em className="italic text-white/90">
                  {children}
                </em>
              ),
            }}
          >
            {justification}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}