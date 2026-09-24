import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import AppHeader from "../../components/LogoHeader";

export default function NotFoundScreen() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col items-center justify-center px-6 text-center">
        <AppHeader
          title="Page not found"
          description="The page you're looking for doesn't exist or may have been moved."
        />

        <div className="mt-10">
          <span className="text-8xl font-semibold tracking-tight text-primary">
            404
          </span>
        </div>

        <Link
          to="/"
          className="group mt-10 inline-flex items-center gap-2 border border-border
                     bg-surface px-6 py-3 text-sm font-medium
                     transition hover:border-primary hover:bg-surface-hover"
        >
          <ArrowLeft
            size={18}
            strokeWidth={1.8}
            className="transition group-hover:-translate-x-1"
          />

          Back to home
        </Link>
      </div>
    </main>
  );
}