import { useState } from "react";
import { Sparkles } from "lucide-react";
import { getRecommendationJustification } from "../services/swipeSessions";

interface WhyRecommendedProps {
  sessionId: string;
  candidateId: string;
}

type Status = "idle" | "loading" | "loaded" | "error";

export default function WhyRecommended({
  sessionId,
  candidateId,
}: WhyRecommendedProps) {
  const [status, setStatus] = useState<Status>("idle");
  const [text, setText] = useState("");

  const handleReveal = async () => {
    setStatus("loading");

    try {
      const result = await getRecommendationJustification(
        sessionId,
        candidateId,
      );

      if (!result.justification) {
        setStatus("error");
        return;
      }

      setText(result.justification);
      setStatus("loaded");
    } catch {
      setStatus("error");
    }
  };

  if (status === "loaded") {
    return (
      <section className="mt-4 border-t border-white/20 pt-3">
        <h4 className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
          <Sparkles size={11} />
          Why this movie
        </h4>

        <p className="mt-1.5 text-xs leading-relaxed text-white/70">
          {text}
        </p>
      </section>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => void handleReveal()}
        disabled={status === "loading"}
        className="flex w-full cursor-pointer items-center justify-center gap-2 border border-dashed border-primary/50 bg-primary/5 px-3 py-2.5 text-xs font-semibold text-primary transition hover:border-primary hover:bg-primary/10 disabled:cursor-wait disabled:opacity-60"
      >
        <Sparkles size={14} />
        {status === "loading" ? "Thinking..." : "Wanna know why?"}
      </button>

      {status === "error" && (
        <p className="mt-2 text-center text-xs text-red-400">
          Couldn't load the explanation right now. Tap to try again.
        </p>
      )}
    </div>
  );
}