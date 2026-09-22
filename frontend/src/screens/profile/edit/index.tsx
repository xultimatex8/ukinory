import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  UserRound,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import {
  changePassword,
  getCurrentUser,
  updateUser,
  type User,
} from "../../../services/user";
import { ApiError } from "../../../services/api";
import AppHeader from "../../../components/LogoHeader";
import {
  passwordSchema,
  profileSchema,
  type PasswordData,
  type ProfileData,
} from "./schema";

export default function EditProfileScreen() {
  const navigate = useNavigate();

  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);

  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register: registerProfileField,
    handleSubmit: handleSubmitProfile,
    reset: resetProfile,
    formState: {
      errors: profileErrors,
      isSubmitting: isSavingProfile,
    },
  } = useForm<ProfileData>({
    resolver: zodResolver(profileSchema),
    mode: "onSubmit",
    reValidateMode: "onSubmit",
  });

  const {
    register: registerPasswordField,
    handleSubmit: handleSubmitPassword,
    reset: resetPassword,
    formState: {
      errors: passwordErrors,
      isSubmitting: isChangingPassword,
    },
  } = useForm<PasswordData>({
    resolver: zodResolver(passwordSchema),
    mode: "onSubmit",
    reValidateMode: "onSubmit",
  });

  useEffect(() => {
    const loadUser = async () => {
      try {
        setIsLoading(true);
        setProfileError(null);

        const [currentUser] = await Promise.all([
          getCurrentUser(),
          new Promise((resolve) => setTimeout(resolve, 350)),
        ]);

        if (currentUser.is_guest) {
          navigate("/profile", { replace: true });
          return;
        }

        setUser(currentUser);

        resetProfile({
          username: currentUser.username,
          email: currentUser.email,
        });
      } catch (error) {
        if (error instanceof ApiError) {
          setProfileError(error.detail);
        } else {
          setProfileError("Unable to load your profile.");
        }
      } finally {
        setIsLoading(false);
      }
    };

    void loadUser();
  }, [navigate, resetProfile]);

  const handleSaveProfile = async (formData: ProfileData) => {
    try {
      setProfileError(null);
      setProfileSuccess(null);

      const updatedUser = await updateUser({
        username: formData.username,
        email: formData.email,
      });

      setUser(updatedUser);

      resetProfile({
        username: updatedUser.username,
        email: updatedUser.email,
      });

      setProfileSuccess("Profile successfully updated.");
    } catch (error) {
      if (error instanceof ApiError) {
        setProfileError(error.detail);
      } else {
        setProfileError("Unable to update your profile.");
      }
    }
  };

  const handleChangePassword = async (formData: PasswordData) => {
    try {
      setPasswordError(null);
      setPasswordSuccess(null);

      await changePassword({
        oldPassword: formData.oldPassword,
        newPassword: formData.newPassword,
      });

      resetPassword();

      setShowOldPassword(false);
      setShowNewPassword(false);
      setShowConfirmPassword(false);

      setPasswordSuccess("Password successfully changed.");
    } catch (error) {
      if (error instanceof ApiError) {
        setPasswordError(error.detail);
      } else {
        setPasswordError("Unable to change your password.");
      }
    }
  };

  const inputClass =
    "w-full border border-border bg-background px-4 py-3 text-sm text-text outline-none transition placeholder:text-text-muted focus:border-primary";

  const passwordInputClass = `${inputClass} pr-12`;

  if (isLoading) {
    return (
      <main className="min-h-screen bg-background text-text">
        <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-6 py-8">
          <section className="flex flex-1 flex-col">
            <AppHeader
              title="Edit your profile"
              description="Manage your account information and password."
            />

            <div className="mt-10 border border-border bg-surface p-6">
              <div className="animate-pulse space-y-6">
                <div>
                  <div className="h-3 w-20 bg-border" />
                  <div className="mt-3 h-10 w-full bg-border" />
                </div>

                <div>
                  <div className="h-3 w-16 bg-border" />
                  <div className="mt-3 h-10 w-full bg-border" />
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="min-h-screen bg-background text-text">
        <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-6 py-8">
          <section className="flex flex-1 flex-col justify-center">
            <AppHeader
              title="Edit your profile"
              description="Manage your account information and password."
            />

            <div className="mt-10 border border-border bg-surface p-5">
              <p className="text-sm text-red-400">
                {profileError ?? "Unable to load your profile."}
              </p>
            </div>

            <Link
              to="/profile"
              className="mt-6 inline-flex items-center gap-2 text-sm text-text-muted transition hover:text-text"
            >
              <ArrowLeft size={16} />
              Back to profile
            </Link>
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-6 py-8">
        <section className="flex flex-1 flex-col justify-center">
          <AppHeader
            title="Edit your profile"
            description="Manage your account information and password."
          />

          <form
            onSubmit={handleSubmitProfile(handleSaveProfile)}
            className="mt-10 border border-border bg-surface"
          >
            <div className="border-b border-border px-6 py-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                Profile information
              </p>
            </div>

            <div className="space-y-6 p-6">
              <div>
                <label
                  htmlFor="username"
                  className="mb-2 block text-sm font-medium"
                >
                  Username
                </label>

                <div className="relative">
                  <UserRound
                    size={18}
                    strokeWidth={1.7}
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted"
                  />

                  <input
                    id="username"
                    type="text"
                    {...registerProfileField("username")}
                    autoComplete="username"
                    aria-invalid={profileErrors.username ? "true" : "false"}
                    className={`${inputClass} pl-11 ${
                      profileErrors.username
                        ? "border-red-400 focus:border-red-400"
                        : ""
                    }`}
                    onChange={() => {
                      setProfileError(null);
                      setProfileSuccess(null);
                    }}
                  />
                </div>

                {profileErrors.username?.message && (
                  <p className="mt-1 text-sm text-red-400">
                    {profileErrors.username.message}
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

                <div className="relative">
                  <Mail
                    size={18}
                    strokeWidth={1.7}
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted"
                  />

                  <input
                    id="email"
                    type="text"
                    {...registerProfileField("email")}
                    autoComplete="email"
                    aria-invalid={profileErrors.email ? "true" : "false"}
                    className={`${inputClass} pl-11 ${
                      profileErrors.email
                        ? "border-red-400 focus:border-red-400"
                        : ""
                    }`}
                    onChange={() => {
                      setProfileError(null);
                      setProfileSuccess(null);
                    }}
                  />
                </div>

                {profileErrors.email?.message && (
                  <p className="mt-1 text-sm text-red-400">
                    {profileErrors.email.message}
                  </p>
                )}
              </div>

              {profileError && (
                <p className="border border-red-400/30 bg-red-400/5 px-4 py-3 text-sm text-red-400">
                  {profileError}
                </p>
              )}

              {profileSuccess && (
                <p className="border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-primary">
                  {profileSuccess}
                </p>
              )}

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={isSavingProfile}
                  className="cursor-pointer bg-primary px-5 py-3 text-sm font-semibold text-background transition hover:bg-primary-hover disabled:cursor-auto disabled:opacity-50"
                >
                  {isSavingProfile ? "Saving..." : "Save changes"}
                </button>
              </div>
            </div>
          </form>

          <form
            onSubmit={handleSubmitPassword(handleChangePassword)}
            className="mt-6 border border-border bg-surface"
          >
            <div className="border-b border-border px-6 py-5">
              <div className="flex items-center gap-3">
                <LockKeyhole
                  size={18}
                  strokeWidth={1.7}
                  className="text-primary"
                />

                <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                  Change password
                </p>
              </div>
            </div>

            <div className="space-y-6 p-6">
              <div>
                <label
                  htmlFor="oldPassword"
                  className="mb-2 block text-sm font-medium"
                >
                  Current password
                </label>

                <div className="relative">
                  <input
                    id="oldPassword"
                    type={showOldPassword ? "text" : "password"}
                    {...registerPasswordField("oldPassword")}
                    autoComplete="current-password"
                    aria-invalid={passwordErrors.oldPassword ? "true" : "false"}
                    className={`${passwordInputClass} ${
                      passwordErrors.oldPassword
                        ? "border-red-400 focus:border-red-400"
                        : ""
                    }`}
                    onChange={() => {
                      setPasswordError(null);
                      setPasswordSuccess(null);
                    }}
                  />

                  <button
                    type="button"
                    onClick={() =>
                      setShowOldPassword((previous) => !previous)
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer p-1 text-text-muted transition hover:text-text"
                    aria-label={
                      showOldPassword
                        ? "Hide current password"
                        : "Show current password"
                    }
                  >
                    {showOldPassword ? (
                      <EyeOff size={19} strokeWidth={1.8} />
                    ) : (
                      <Eye size={19} strokeWidth={1.8} />
                    )}
                  </button>
                </div>

                {passwordErrors.oldPassword?.message && (
                  <p className="mt-1 text-sm text-red-400">
                    {passwordErrors.oldPassword.message}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="newPassword"
                  className="mb-2 block text-sm font-medium"
                >
                  New password
                </label>

                <div className="relative">
                  <input
                    id="newPassword"
                    type={showNewPassword ? "text" : "password"}
                    {...registerPasswordField("newPassword")}
                    autoComplete="new-password"
                    aria-invalid={passwordErrors.newPassword ? "true" : "false"}
                    className={`${passwordInputClass} ${
                      passwordErrors.newPassword
                        ? "border-red-400 focus:border-red-400"
                        : ""
                    }`}
                    onChange={() => {
                      setPasswordError(null);
                      setPasswordSuccess(null);
                    }}
                  />

                  <button
                    type="button"
                    onClick={() =>
                      setShowNewPassword((previous) => !previous)
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer p-1 text-text-muted transition hover:text-text"
                    aria-label={
                      showNewPassword
                        ? "Hide new password"
                        : "Show new password"
                    }
                  >
                    {showNewPassword ? (
                      <EyeOff size={19} strokeWidth={1.8} />
                    ) : (
                      <Eye size={19} strokeWidth={1.8} />
                    )}
                  </button>
                </div>

                {passwordErrors.newPassword?.message && (
                  <p className="mt-1 text-sm text-red-400">
                    {passwordErrors.newPassword.message}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="confirmPassword"
                  className="mb-2 block text-sm font-medium"
                >
                  Confirm new password
                </label>

                <div className="relative">
                  <input
                    id="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    {...registerPasswordField("confirmPassword")}
                    autoComplete="new-password"
                    aria-invalid={
                      passwordErrors.confirmPassword ? "true" : "false"
                    }
                    className={`${passwordInputClass} ${
                      passwordErrors.confirmPassword
                        ? "border-red-400 focus:border-red-400"
                        : ""
                    }`}
                    onChange={() => {
                      setPasswordError(null);
                      setPasswordSuccess(null);
                    }}
                  />

                  <button
                    type="button"
                    onClick={() =>
                      setShowConfirmPassword((previous) => !previous)
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer p-1 text-text-muted transition hover:text-text"
                    aria-label={
                      showConfirmPassword
                        ? "Hide confirm password"
                        : "Show confirm password"
                    }
                  >
                    {showConfirmPassword ? (
                      <EyeOff size={19} strokeWidth={1.8} />
                    ) : (
                      <Eye size={19} strokeWidth={1.8} />
                    )}
                  </button>
                </div>

                {passwordErrors.confirmPassword?.message && (
                  <p className="mt-1 text-sm text-red-400">
                    {passwordErrors.confirmPassword.message}
                  </p>
                )}
              </div>

              {passwordError && (
                <p className="border border-red-400/30 bg-red-400/5 px-4 py-3 text-sm text-red-400">
                  {passwordError}
                </p>
              )}

              {passwordSuccess && (
                <p className="border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-primary">
                  {passwordSuccess}
                </p>
              )}

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={isChangingPassword}
                  className="cursor-pointer bg-primary px-5 py-3 text-sm font-semibold text-background transition hover:bg-primary-hover disabled:cursor-auto disabled:opacity-50"
                >
                  {isChangingPassword
                    ? "Changing password..."
                    : "Change password"}
                </button>
              </div>
            </div>
          </form>

          <div className="mt-6">
            <Link
              to="/profile"
              className="inline-flex items-center gap-2 text-sm text-text-muted transition hover:text-text"
            >
              <ArrowLeft size={16} />
              Back to profile
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}