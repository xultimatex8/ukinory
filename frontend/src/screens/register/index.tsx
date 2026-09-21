import { useState } from "react";
import {
  Link,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Eye, EyeOff } from "lucide-react";

import { ApiError } from "../../services/api";
import { register } from "../../services/auth";
import { claimGuest } from "../../services/user";
import { registerSchema, type RegisterData } from "./schema";
import AppHeader from "../../components/LogoHeader";
import { useLegalDocuments } from "../../hooks/useLegalDocuments";
import LegalLinks from "../../components/legal/LegalLinks";

export default function RegisterScreen() {
  const navigate = useNavigate();
  const location = useLocation();

  const isClaiming = location.pathname === "/register/claim";
  const destination = location.state?.from ?? { pathname: "/" };

  const {
    documents,
    error: documentsError,
    reload: reloadDocuments,
  } = useLegalDocuments();

  const {
    register: registerField,
    handleSubmit,
    setError,
    setValue,
    clearErrors,
    formState: { errors, isSubmitting },
  } = useForm<RegisterData>({
    resolver: zodResolver(registerSchema),
    mode: "onSubmit",
    reValidateMode: "onSubmit",
    defaultValues: { acceptedTerms: false },
  });

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const handleSubmitForm = async (formData: RegisterData) => {
    if (!documents) {
      setError("root", {
        type: "server",
        message:
          "Unable to load the Terms and Conditions. Please try again.",
      });
      return;
    }

    try {
      const payload = {
        email: formData.email,
        username: formData.username,
        password: formData.password,
        accepted_documents: documents.map((document) => document.id),
      };

      const data = isClaiming
        ? await claimGuest(payload)
        : await register(payload);

      localStorage.setItem("access_token", data.access);
      localStorage.setItem("refresh_token", data.refresh);

      navigate(destination, { replace: true });
    } catch (error) {
      if (typeof error === "object" && error !== null) {
        const backendErrors = (
          error instanceof ApiError ? error.fields : error
        ) as Record<string, string[] | string>;

        Object.entries(backendErrors).forEach(([field, messages]) => {
          if (
            field === "username" ||
            field === "email" ||
            field === "password"
          ) {
            setError(field, {
              type: "server",
              message: Array.isArray(messages) ? messages[0] : messages,
            });
          } else if (field === "accepted_documents") {
            setValue("acceptedTerms", false);
            setError("acceptedTerms", {
              type: "server",
              message:
                "The Terms and Conditions or Privacy Policy have changed. Please review them and accept again.",
            });
            void reloadDocuments();
          }
        });

        const detail = Array.isArray(backendErrors.detail)
          ? backendErrors.detail[0]
          : backendErrors.detail;

        if (detail) {
          setError("root", {
            type: "server",
            message: detail,
          });
        }
      } else {
        setError("root", {
          type: "server",
          message: isClaiming
            ? "Unable to claim your account."
            : "Unable to create your account.",
        });
      }
    }
  };

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6">
        <AppHeader
          title={isClaiming ? "Claim your account" : "Create your account"}
          description={
            isClaiming
              ? "Create an account to keep the activity and movie preferences you have already built up."
              : "Start discovering movies tailored to your taste."
          }
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
                htmlFor="username"
                className="mb-2 block text-sm font-medium"
              >
                Username
              </label>

              <input
                id="username"
                type="text"
                {...registerField("username", {
                  onChange: () => clearErrors("username"),
                })}
                autoComplete="username"
                className="w-full border border-border bg-background px-4 py-3
                           text-text outline-none transition
                           focus:border-primary"
              />

              {errors.username?.message && (
                <p className="mt-1 text-sm text-red-400">
                  {errors.username.message}
                </p>
              )}
            </div>

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
                  autoComplete="new-password"
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

            <div>
              <label
                htmlFor="confirmPassword"
                className="mb-2 block text-sm font-medium"
              >
                Confirm password
              </label>

              <div className="relative">
                <input
                  id="confirmPassword"
                  type={showConfirmPassword ? "text" : "password"}
                  {...registerField("confirmPassword", {
                    onChange: () => clearErrors("confirmPassword"),
                  })}
                  autoComplete="new-password"
                  className="w-full border border-border bg-background px-4 py-3 pr-12
                             text-text outline-none transition
                             focus:border-primary"
                />

                <button
                  type="button"
                  onClick={() =>
                    setShowConfirmPassword((previous) => !previous)
                  }
                  className="absolute right-3 top-1/2 -translate-y-1/2
                             cursor-pointer text-text-muted transition
                             hover:text-text"
                  aria-label={
                    showConfirmPassword
                      ? "Hide confirm password"
                      : "Show confirm password"
                  }
                >
                  {showConfirmPassword ? (
                    <EyeOff size={20} />
                  ) : (
                    <Eye size={20} />
                  )}
                </button>
              </div>

              {errors.confirmPassword?.message && (
                <p className="mt-1 text-sm text-red-400">
                  {errors.confirmPassword.message}
                </p>
              )}
            </div>

            <div>
              <div className="flex items-start gap-3">
                <input
                  id="acceptedTerms"
                  type="checkbox"
                  {...registerField("acceptedTerms", {
                    onChange: () => clearErrors("acceptedTerms"),
                  })}
                  className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-primary"
                />

                <label
                  htmlFor="acceptedTerms"
                  className="text-sm leading-relaxed text-text-muted"
                >
                  I accept the <LegalLinks documents={documents} />.
                </label>
              </div>

              {errors.acceptedTerms?.message && (
                <p className="mt-1 text-sm text-red-400">
                  {errors.acceptedTerms.message}
                </p>
              )}

              {documentsError && (
                <p className="mt-1 text-sm text-red-400">
                  {documentsError}{" "}
                  <button
                    type="button"
                    onClick={() => void reloadDocuments()}
                    className="cursor-pointer font-medium underline"
                  >
                    Try again
                  </button>
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
            disabled={isSubmitting || !documents}
            className="mt-6 w-full cursor-pointer bg-primary px-4 py-3
                       font-semibold text-background transition
                       hover:bg-primary-hover disabled:cursor-auto
                       disabled:opacity-50 disabled:hover:bg-primary"
          >
            {isSubmitting
              ? isClaiming
                ? "Claiming account..."
                : "Creating account..."
              : isClaiming
                ? "Claim account"
                : "Create account"}
          </button>

          {!isClaiming && (
            <p className="mt-6 text-center text-sm text-text-muted">
              Already have an account?{" "}
              <Link
                to="/login"
                className="font-medium text-primary transition hover:text-primary-hover"
              >
                Sign in
              </Link>
            </p>
          )}
        </form>
      </div>
    </main>
  );
}