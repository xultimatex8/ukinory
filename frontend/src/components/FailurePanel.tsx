import { Loader2 } from "lucide-react";

interface FailurePanelProps {
  title: string;
  text: string;
  onRetry: () => void;
  isRetrying?: boolean;
}

export default function FailurePanel({
  title,
  text,
  onRetry,
  isRetrying = false,
}: FailurePanelProps) {
  return (
    <div className="border border-border bg-surface px-6 py-10 text-center">
      <h2 className="text-lg font-semibold">{title}</h2>

      <p className="mt-2 text-sm text-text-muted">{text}</p>

      <button
        type="button"
        disabled={isRetrying}
        onClick={onRetry}
        className="mt-5 inline-flex cursor-pointer items-center gap-2 border border-primary px-5 py-2.5 text-sm font-medium text-primary transition hover:bg-primary hover:text-background disabled:cursor-auto disabled:opacity-40"
      >
        {isRetrying && <Loader2 size={15} className="animate-spin" />}
        Try again
      </button>
    </div>
  );
}