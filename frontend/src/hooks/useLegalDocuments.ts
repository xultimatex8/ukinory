import { useCallback, useEffect, useState } from "react";

import {
  getCurrentLegalDocuments,
  type LegalDocument,
} from "../services/legal";

export function useLegalDocuments() {
  const [documents, setDocuments] = useState<LegalDocument[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await getCurrentLegalDocuments();

      if (result.length === 0) {
        throw new Error("No legal documents published");
      }

      setDocuments(result);
    } catch {
      setError("Unable to load the Terms and Conditions and Privacy Policy.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const result = await getCurrentLegalDocuments();

        if (result.length === 0) {
          throw new Error("No legal documents published");
        }

        if (!cancelled) {
          setDocuments(result);
        }
      } catch {
        if (!cancelled) {
          setError(
            "Unable to load the Terms and Conditions and Privacy Policy.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  return { documents, isLoading, error, reload };
}