import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { endSwipeSession } from "../services/swipeSessions";
import { getErrorMessage } from "../utils/errors";

interface UseEndSwipeSessionParams {
  id: string | undefined;
}

interface UseEndSwipeSessionResult {
  isEndingSession: boolean;
  endSessionError: string | null;
  clearEndSessionError: () => void;
  handleGoHome: () => void;
  handleDownloadCsv: () => void;
}

function downloadBlob(blob: Blob, filename: string) {
  const downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = downloadUrl;
  link.download = filename;

  document.body.appendChild(link);
  link.click();
  link.remove();

  setTimeout(() => {
    URL.revokeObjectURL(downloadUrl);
  }, 1000);
}

export function useEndSwipeSession({
  id,
}: UseEndSwipeSessionParams): UseEndSwipeSessionResult {
  const navigate = useNavigate();

  const [isEndingSession, setIsEndingSession] = useState(false);
  const [endSessionError, setEndSessionError] = useState<string | null>(null);

  const clearEndSessionError = useCallback(() => {
    setEndSessionError(null);
  }, []);

  const handleEndSession = useCallback(
    async (downloadCsv: boolean) => {
      if (!id || isEndingSession) return;

      setIsEndingSession(true);
      setEndSessionError(null);

      try {
        const csvBlob = await endSwipeSession(id);

        if (downloadCsv) {
          downloadBlob(csvBlob, "ukinory_watchlist.csv");
        }

        navigate("/");
      } catch (err) {
        setEndSessionError(getErrorMessage(err));
      } finally {
        setIsEndingSession(false);
      }
    },
    [id, isEndingSession, navigate],
  );

  const handleGoHome = useCallback(() => {
    void handleEndSession(false);
  }, [handleEndSession]);

  const handleDownloadCsv = useCallback(() => {
    void handleEndSession(true);
  }, [handleEndSession]);

  return {
    isEndingSession,
    endSessionError,
    clearEndSessionError,
    handleGoHome,
    handleDownloadCsv,
  };
}
