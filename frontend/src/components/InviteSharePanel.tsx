import { useEffect, useState } from "react";
import { Check, Copy, Link as LinkIcon, RefreshCw } from "lucide-react";

import { regenerateInvite, type Invite } from "../services/comparisons";
import { getErrorMessage } from "../utils/errors";

interface InviteSharePanelProps {
  roomId: string;
  initialInvite: Invite | null;
}

function formatRemaining(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export default function InviteSharePanel({
  roomId,
  initialInvite,
}: InviteSharePanelProps) {
  const [invite, setInvite] = useState<Invite | null>(initialInvite);
  const [now, setNow] = useState(() => Date.now());
  const [copied, setCopied] = useState<"code" | "link" | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const remainingMs = invite ? new Date(invite.expires_at).getTime() - now : 0;
  const isExpired = !invite || remainingMs <= 0;
  const link = invite
    ? `${window.location.origin}/comparison/join/${invite.code}`
    : "";

  const copy = async (kind: "code" | "link", value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(kind);
      window.setTimeout(() => setCopied(null), 1800);
    } catch {
      setError("Couldn't copy automatically. Select the text and copy it.");
    }
  };

  const handleRegenerate = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setError(null);
    try {
      setInvite(await regenerateInvite(roomId));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="border border-border bg-surface p-5">
      {invite && !isExpired ? (
        <>
          <p className="text-xs text-text-muted">Invite code</p>
          <div className="mt-2 flex items-stretch gap-2">
            <code className="min-w-0 flex-1 truncate border border-border bg-background px-3 py-2.5 text-sm text-text">
              {invite.code}
            </code>
            <button
              type="button"
              onClick={() => void copy("code", invite.code)}
              aria-label="Copy code"
              className="flex w-11 cursor-pointer items-center justify-center border border-border bg-background text-text-secondary transition hover:border-primary hover:text-primary"
            >
              {copied === "code" ? <Check size={16} /> : <Copy size={16} />}
            </button>
          </div>

          <p className="mt-4 text-xs text-text-muted">Invite link</p>
          <div className="mt-2 flex items-stretch gap-2">
            <code className="min-w-0 flex-1 truncate border border-border bg-background px-3 py-2.5 text-xs text-text-secondary">
              {link}
            </code>
            <button
              type="button"
              onClick={() => void copy("link", link)}
              aria-label="Copy link"
              className="flex w-11 cursor-pointer items-center justify-center border border-border bg-background text-text-secondary transition hover:border-primary hover:text-primary"
            >
              {copied === "link" ? <Check size={16} /> : <LinkIcon size={16} />}
            </button>
          </div>

          <p className="mt-4 text-xs leading-relaxed text-text-muted">
            Expires in {formatRemaining(remainingMs)}. Your friend can open the
            link or type the code on the Taste comparison page — no account
            needed.
          </p>
        </>
      ) : (
        <p className="text-sm leading-relaxed text-text-secondary">
          {invite
            ? "This invite has expired."
            : "The invite for this room isn't available here anymore."}{" "}
          Generate a new one to keep waiting.
        </p>
      )}

      <button
        type="button"
        disabled={isRefreshing}
        onClick={() => void handleRegenerate()}
        className="mt-4 flex cursor-pointer items-center gap-2 border border-border bg-background px-3.5 py-2 text-xs font-medium text-text-secondary transition hover:border-primary hover:text-primary disabled:cursor-auto disabled:opacity-40"
      >
        <RefreshCw size={13} className={isRefreshing ? "animate-spin" : ""} />
        {invite && !isExpired ? "Replace with a new invite" : "Generate new invite"}
      </button>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
    </div>
  );
}