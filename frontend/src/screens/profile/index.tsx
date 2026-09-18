import { useEffect, useState } from "react";
import {
  ArrowLeft,
  LogOut,
  Mail,
  UserRound,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import AppHeader from "../../components/LogoHeader";
import {
  deleteAccount,
  getCurrentUser,
  signOut,
  type User,
} from "../../services/user";
import { ApiError } from "../../services/api";
import DeleteAccountModal from "../../components/DeleteAccountModal";

export default function ProfileScreen() {
  const navigate = useNavigate();

  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    const loadUser = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const currentUser = await getCurrentUser();
        setUser(currentUser);
      } catch (error) {
        if (error instanceof ApiError) {
          setError(error.detail);
        } else {
          setError("Unable to load your profile.");
        }
      } finally {
        setIsLoading(false);
      }
    };

    void loadUser();
  }, []);

  const handleLogout = async () => {
    try {
      await signOut();
    } finally {
      navigate("/");
    }
  };

  const handleDeleteAccount = async (password?: string) => {
    try {
      setIsDeleting(true);
      setDeleteError(null);

      await deleteAccount(password);

      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");

      navigate("/auth", { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        setDeleteError(error.detail);
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const handleOpenDeleteModal = () => {
    setDeleteError(null);
    setIsDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    if (isDeleting) {
      return;
    }

    setIsDeleteModalOpen(false);
    setDeleteError(null);
  };

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-6 py-8">
        <section className="flex flex-1 flex-col justify-center">
          <AppHeader
            title="Your profile"
            description="View your account information."
          />

          {isLoading && (
            <div className="mt-10 border border-border bg-surface p-6">
              <div className="animate-pulse space-y-6">
                <div>
                  <div className="h-3 w-20 bg-border" />
                  <div className="mt-3 h-5 w-40 bg-border" />
                </div>

                <div>
                  <div className="h-3 w-16 bg-border" />
                  <div className="mt-3 h-5 w-56 bg-border" />
                </div>
              </div>
            </div>
          )}

          {error && !isLoading && (
            <div className="mt-10 border border-border bg-surface p-5">
              <p className="text-sm text-red-400">
                {error}
              </p>
            </div>
          )}

          {user && !isLoading && !error && (
            <div className="mt-10 border border-border bg-surface">
              <div className="border-b border-border px-6 py-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                  Account information
                </p>
              </div>

              <div className="divide-y divide-border">
                <div className="flex items-center gap-4 px-6 py-5">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-border bg-background text-primary">
                    <UserRound
                      size={18}
                      strokeWidth={1.7}
                    />
                  </div>

                  <div className="min-w-0">
                    <p className="text-xs text-text-muted">
                      Username
                    </p>

                    <p className="mt-1 truncate text-sm font-medium text-text">
                      {user.username}
                    </p>
                  </div>
                </div>

                {!user.is_guest && (
                  <div className="flex items-center gap-4 px-6 py-5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-border bg-background text-primary">
                      <Mail
                        size={18}
                        strokeWidth={1.7}
                      />
                    </div>

                    <div className="min-w-0">
                      <p className="text-xs text-text-muted">
                        Email
                      </p>

                      <p className="mt-1 truncate text-sm font-medium text-text">
                        {user.email}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {user.is_guest && (
                <div className="border-t border-border px-6 py-5">
                  <div className="border border-primary/20 bg-primary/5 p-4">
                    <p className="text-sm font-medium text-primary">
                      Claim your account
                    </p>

                    <p className="mt-1 text-sm leading-relaxed text-text-muted">
                      Guest accounts are temporary and are automatically
                      deleted after a period of inactivity. Register with
                      Claim account to keep your activity and movie preferences
                      permanently.
                    </p>

                    <Link
                      to="/register/claim"
                      className="mt-4 inline-block bg-primary px-4 py-2 text-sm font-semibold text-background transition hover:bg-primary-hover"
                    >
                      Claim account
                    </Link>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="mt-6 flex items-center justify-between">
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-sm text-text-muted transition hover:text-text"
            >
              <ArrowLeft size={16} />
              Back to home
            </Link>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleOpenDeleteModal}
                disabled={isDeleting}
                className="cursor-pointer border border-red-400/40 px-4 py-2 text-sm font-medium text-red-400 transition hover:border-red-400 hover:bg-red-400/5 hover:text-red-300 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Delete account
              </button>

              <button
                type="button"
                onClick={handleLogout}
                disabled={isDeleting}
                className="flex cursor-pointer items-center gap-2 border border-border px-4 py-2 text-sm font-medium text-text-muted transition hover:border-text-muted hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
              >
                <LogOut size={16} />
                Sign out
              </button>
            </div>
          </div>
        </section>
      </div>

      {isDeleteModalOpen && user && (
        <DeleteAccountModal
          isDeleting={isDeleting}
          isGuest={user.is_guest}
          error={deleteError}
          onClose={handleCloseDeleteModal}
          onConfirm={handleDeleteAccount}
        />
      )}
    </main>
  );
}