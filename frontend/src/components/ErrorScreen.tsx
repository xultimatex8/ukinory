import { AlertCircle } from "lucide-react";

interface ErrorScreenProps {
  title?: string;
  message: string;
  buttonText?: string;
  onRetry?: () => void;
  onBack?: () => void;
}

export default function ErrorScreen({
  title = "Something went wrong",
  message,
  buttonText = "Try again",
  onRetry,
  onBack,
}: ErrorScreenProps) {
  const handleButtonClick = onRetry ?? onBack;

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <AlertCircle
          size={42}
          strokeWidth={1.5}
          className="text-text-muted"
        />

        <h2 className="mt-5 text-2xl font-bold">{title}</h2>

        <p className="mt-3 max-w-md text-sm leading-relaxed text-text-muted">
          {message}
        </p>

        {handleButtonClick && (
          <button
            type="button"
            onClick={handleButtonClick}
            className="mt-6 flex cursor-pointer items-center justify-center border border-primary px-5 py-2.5 text-sm font-medium text-primary transition hover:bg-primary hover:text-background"
          >
            {buttonText}
          </button>
        )}
      </div>
    </main>
  );
}
