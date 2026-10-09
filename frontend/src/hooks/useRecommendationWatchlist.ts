import { useCallback, useState } from "react";

import {
  addRecommendationToWatchlist,
  exportRecommendationsWatchlist,
  removeRecommendationFromWatchlist,
  type JointRecommendation,
} from "../services/comparisons";
import { getErrorMessage } from "../utils/errors";

export function useRecommendationWatchlist(
  roomId: string,
  recommendations: JointRecommendation[],
) {
  const [saved, setSaved] = useState<Set<string>>(
    () =>
      new Set(
        recommendations
          .filter((r) => r.in_watchlist)
          .map((r) => String(r.movie_id)),
      ),
  );
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  const toggle = useCallback(
    async (movieId: string | number) => {
      const key = String(movieId);
      if (pending.has(key)) return;

      const wasSaved = saved.has(key);

      setPending((p) => new Set(p).add(key));
      setSaved((s) => {
        const next = new Set(s);
        if (wasSaved) next.delete(key);
        else next.add(key);
        return next;
      });
      setError(null);

      try {
        if (wasSaved) await removeRecommendationFromWatchlist(roomId, movieId);
        else await addRecommendationToWatchlist(roomId, movieId);
      } catch (err) {
        setSaved((s) => {
          const next = new Set(s);
          if (wasSaved) next.add(key);
          else next.delete(key);
          return next;
        });
        setError(getErrorMessage(err));
      } finally {
        setPending((p) => {
          const next = new Set(p);
          next.delete(key);
          return next;
        });
      }
    },
    [roomId, saved, pending],
  );

  const exportCsv = useCallback(async () => {
    setIsExporting(true);
    setError(null);

    try {
      const blob = await exportRecommendationsWatchlist(roomId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "ukinory_comparison_watchlist.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsExporting(false);
    }
  }, [roomId]);

  const isSaved = useCallback(
    (id: string | number) => saved.has(String(id)),
    [saved],
  );
  const isPending = useCallback(
    (id: string | number) => pending.has(String(id)),
    [pending],
  );

  return {
    isSaved,
    isPending,
    savedCount: saved.size,
    toggle,
    exportCsv,
    isExporting,
    error,
  };
}