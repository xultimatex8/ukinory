import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import ErrorScreen from "../../../components/ErrorScreen";
import { ApiError } from "../../../services/api";
import { createGuest } from "../../../services/auth";
import { getErrorMessage } from "../../../utils/errors";
import { acceptInvite } from "../../../services/invites";

async function ensureSession(): Promise<void> {
  if (
    localStorage.getItem("access_token") &&
    localStorage.getItem("refresh_token")
  ) {
    return;
  }

  const { access, refresh } = await createGuest();
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return "This invite doesn't exist.";
    if (err.status === 410) return "This invite has expired. Ask your friend for a new one.";
    return err.detail;
  }
  return getErrorMessage(err);
}

export default function JoinComparisonScreen() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!code || startedRef.current) return;
    startedRef.current = true;

    const join = async () => {
      try {
        await ensureSession();
        const accepted = await acceptInvite(code);
        navigate(`/comparison/room/${accepted.target.id}`, { replace: true });
      } catch (err) {
        setError(messageFor(err));
      }
    };

    void join();
  }, [code, navigate]);

  if (error) {
    return <ErrorScreen message={error} buttonText="Back to home" />;
  }

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <Loader2 size={28} className="animate-spin text-primary" />
        <h1 className="mt-4 text-lg font-semibold">Joining the room…</h1>
        <p className="mt-2 text-sm text-text-muted">
          You'll be taken there in a moment.
        </p>
      </div>
    </main>
  );
}