import { Link, useLocation, useNavigate } from "react-router-dom";
import { Clapperboard, UserRound } from "lucide-react";

import AppHeader from "../../components/LogoHeader";
import { createGuest } from "../../services/auth";

export default function AuthScreen() {
  const navigate = useNavigate();
  const location = useLocation();

  const destination = location.state?.from ?? { pathname: "/" };

  const handleGuest = async () => {
    try {
      const data = await createGuest();

      localStorage.setItem("access_token", data.access);
      localStorage.setItem("refresh_token", data.refresh);

      navigate(destination, { replace: true });
    } catch (error) {
      console.error("Unable to create guest session:", error);
    }
  };

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col justify-center px-6">
        <AppHeader
          title="Find what you want to watch"
          description="Discover movies tailored to your taste and find your next favorite."
        />

        <div className="mt-12 grid gap-4 sm:grid-cols-2">
          <button
            type="button"
            onClick={handleGuest}
            className="group cursor-pointer border border-border bg-surface p-8
                       text-center transition hover:border-primary
                       hover:bg-surface-hover"
          >
            <div className="mx-auto flex h-20 w-20 items-center justify-center">
              <Clapperboard
                size={72}
                strokeWidth={1.5}
                className="text-primary transition group-hover:scale-105"
              />
            </div>

            <h2 className="mt-7 text-xl font-semibold">
              Explore as a guest
            </h2>

            <p className="mt-2 text-sm text-text-muted">
              Get started without an account
            </p>
          </button>

          <Link
            to="/login"
            state={{ from: destination }}
            className="group border border-border bg-surface p-8
                       text-center transition hover:border-primary
                       hover:bg-surface-hover"
          >
            <div className="mx-auto flex h-20 w-20 items-center justify-center">
              <UserRound
                size={72}
                strokeWidth={1.5}
                className="text-primary transition group-hover:scale-105"
              />
            </div>

            <h2 className="mt-7 text-xl font-semibold">
              Welcome back
            </h2>

            <p className="mt-2 text-sm text-text-muted">
              Sign in to your account
            </p>
          </Link>
        </div>

        <div className="mt-8 text-center">
          <span className="text-sm text-text-muted">
            Don't have an account?{" "}
          </span>

          <Link
            to="/register"
            state={{ from: destination }}
            className="text-sm font-medium text-primary transition hover:text-primary-hover"
          >
            Create one
          </Link>
        </div>
      </div>
    </main>
  );
}
