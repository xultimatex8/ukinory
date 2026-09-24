import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { ArrowLeft, Eye, EyeOff } from "lucide-react";

import { login } from "../../services/auth";
import AppHeader from "../../components/LogoHeader";
import { loginSchema, type LoginData } from "./schema";

export default function LoginScreen() {
  const navigate = useNavigate();
  const location = useLocation();

  const destination = location.state?.from ?? { pathname: "/" };

  const {
    register: registerField,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors, isSubmitting },
  } = useForm<LoginData>({
    resolver: zodResolver(loginSchema),
    mode: "onSubmit",
    reValidateMode: "onSubmit",
  });

  const [showPassword, setShowPassword] = useState(false);

  const handleSubmitForm = async (formData: LoginData) => {
    try {
      const data = await login(formData);

      localStorage.setItem("access_token", data.access);
      localStorage.setItem("refresh_token", data.refresh);

      navigate(destination, { replace: true });
    } catch (error) {
      if (typeof error === "object" && error !== null) {
        const backendErrors = error as {
          email?: string[];
          password?: string[];
          detail?: string;
        };

        if (backendErrors.email?.[0]) {
          setError("email", {
            type: "server",
            message: backendErrors.email[0],
          });
        }

        if (backendErrors.password?.[0]) {
          setError("password", {
            type: "server",
            message: backendErrors.password[0],
          });
        }

        if (backendErrors.detail) {
          setError("root", {
            type: "server",
            message: backendErrors.detail + ".",
          });
        }
      } else {
        setError("root", {
          type: "server",
          message: "Unable to sign in.",
        });
      }
}
  };

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6">
        <AppHeader
          title="Welcome back"
          description="Sign in to continue discovering movies tailored to your taste."
        />

        <button
          type="button"
          onClick={() => navigate(-1)}
          className="mt-6 flex w-fit cursor-pointer items-center gap-2
                     text-sm text-text-muted transition hover:text-text"
        >
          <ArrowLeft size={17} strokeWidth={1.8} />
          Back
        </button>

        <form
          onSubmit={handleSubmit(handleSubmitForm)}
          className="mt-3 border border-border bg-surface p-8"
        >
          <div className="space-y-5">
            <div>
              <label
                htmlFor="email"
                className="mb-2 block text-sm font-medium"
              >
                Email
              </label>

              <input
                id="email"
                type="text"
                {...registerField("email", {
                  onChange: () => clearErrors("email"),
                })}
                autoComplete="email"
                className="w-full border border-border bg-background px-4 py-3
                           text-text outline-none transition
                           focus:border-primary"
              />

              {errors.email?.message && (
                <p className="mt-1 text-sm text-red-400">
                  {errors.email.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-2 block text-sm font-medium"
              >
                Password
              </label>

              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  {...registerField("password", {
                    onChange: () => clearErrors("password"),
                  })}
                  autoComplete="current-password"
                  className="w-full border border-border bg-background px-4 py-3 pr-12
                             text-text outline-none transition
                             focus:border-primary"
                />

                <button
                  type="button"
                  onClick={() => setShowPassword((previous) => !previous)}
                  className="absolute right-3 top-1/2 -translate-y-1/2
                             cursor-pointer text-text-muted transition
                             hover:text-text"
                  aria-label={
                    showPassword ? "Hide password" : "Show password"
                  }
                >
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>

              {errors.password?.message && (
                <p className="mt-1 text-sm text-red-400">
                  {errors.password.message}
                </p>
              )}
            </div>

            {errors.root?.message && (
              <p className="text-sm text-red-400">
                {errors.root.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-6 w-full cursor-pointer bg-primary px-4 py-3
                       font-semibold text-background transition
                       hover:bg-primary-hover disabled:cursor-auto
                       disabled:opacity-50"
          >
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>

          <p className="mt-6 text-center text-sm text-text-muted">
            Don't have an account?{" "}
            <Link
              to="/register"
              className="font-medium text-primary transition hover:text-primary-hover"
            >
              Create one
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}