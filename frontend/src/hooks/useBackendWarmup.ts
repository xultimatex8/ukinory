import { useEffect, useState } from "react";

import { apiUrl } from "../api";

export type BackendStatus = "checking" | "waking" | "ready" | "unreachable";

const SLOW_THRESHOLD_MS = 2_000;
const REQUEST_TIMEOUT_MS = 5_000;
const RETRY_DELAY_MS = 1_500;
const UNREACHABLE_AFTER_MS = 2 * 60 * 1000;
const UNREACHABLE_RETRY_MS = 5_000;

export function useBackendWarmup(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    let retryTimer: number | undefined;
    const startedAt = Date.now();

    const slowTimer = window.setTimeout(() => {
      setStatus((current) => (current === "checking" ? "waking" : current));
    }, SLOW_THRESHOLD_MS);

    const schedule = (delay: number) => {
      window.clearTimeout(retryTimer);
      retryTimer = window.setTimeout(() => void ping(), delay);
    };

    const ping = async () => {
      if (cancelled || inFlight) return;

      inFlight = true;
      const controller = new AbortController();
      const abortTimer = window.setTimeout(
        () => controller.abort(),
        REQUEST_TIMEOUT_MS,
      );

      try {
        const response = await fetch(apiUrl("/health/"), {
          method: "GET",
          cache: "no-store",
          signal: controller.signal,
        });

        if (!response.ok) throw new Error(`Health check: ${response.status}`);

        if (!cancelled) {
          window.clearTimeout(slowTimer);
          window.clearTimeout(retryTimer);
          setStatus("ready");
        }
        return;
      } catch {
        // Backend is asleep or starting up: retry.
      } finally {
        window.clearTimeout(abortTimer);
        inFlight = false;
      }

      if (cancelled) return;

      if (Date.now() - startedAt >= UNREACHABLE_AFTER_MS) {
        window.clearTimeout(slowTimer);
        setStatus("unreachable");
        schedule(UNREACHABLE_RETRY_MS);
        return;
      }

      setStatus((current) => (current === "checking" ? "waking" : current));
      schedule(RETRY_DELAY_MS);
    };

    const wakeUpNow = () => {
      if (document.visibilityState === "visible") void ping();
    };

    window.addEventListener("online", wakeUpNow);
    document.addEventListener("visibilitychange", wakeUpNow);

    void ping();

    return () => {
      cancelled = true;
      window.clearTimeout(slowTimer);
      window.clearTimeout(retryTimer);
      window.removeEventListener("online", wakeUpNow);
      document.removeEventListener("visibilitychange", wakeUpNow);
    };
  }, []);

  return status;
}