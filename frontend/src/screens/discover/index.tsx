import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  FileArchive,
  FileText,
  Heart,
  Trash2,
  Upload,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import AppHeader from "../../components/LogoHeader";
import {
  createIndividualSwipeSession,
  startSwipeSession,
} from "../../services/swipeSessions";
import { importExport, type ImportResult } from "../../services/imports";
import { getLibraryStats, type LibraryStats } from "../../services/library";

export default function DiscoverScreen() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [libraryStats, setLibraryStats] = useState<LibraryStats | null>(null);
  const [isLoadingLibraryStats, setIsLoadingLibraryStats] = useState(true);

  const hasLibraryData =
    libraryStats === null ? null : libraryStats.rated_total > 0;

  const refreshLibraryStats = async () => {
    try {
      setLibraryStats(await getLibraryStats());
    } catch {
      setLibraryStats(null);
    }
  };

  useEffect(() => {
    const loadLibraryStats = async () => {
      try {
        setIsLoadingLibraryStats(true);

        const [stats] = await Promise.all([
          getLibraryStats(),
          new Promise((resolve) => setTimeout(resolve, 350)),
        ]);

        setLibraryStats(stats);
      } catch {
        setLibraryStats(null);
      } finally {
        setIsLoadingLibraryStats(false);
      }
    };

    void loadLibraryStats();
  }, []);

  const handleCreateSession = async () => {
    setIsCreatingSession(true);
    setImportResult(null);
    setError(null);

    try {
      const session = await createIndividualSwipeSession();
      const started = await startSwipeSession(session.id);
      navigate(`/discover/${session.id}`, {
        state: { leaveToken: started.leave_token },
      });
    } catch {
      setError("Unable to start a swipe session.");
    } finally {
      setIsCreatingSession(false);
    }
  };

  const addFiles = (files: File[]) => {
    if (!files.length || isImporting) return;

    setImportResult(null);
    setError(null);

    setPendingFiles((currentFiles) => {
      const existingFiles = new Set(
        currentFiles.map(
          (file) => `${file.name}-${file.size}-${file.lastModified}`,
        ),
      );

      const newFiles = files.filter(
        (file) =>
          !existingFiles.has(
            `${file.name}-${file.size}-${file.lastModified}`,
          ),
      );

      return [...currentFiles, ...newFiles];
    });
  };

  const removeFile = (fileToRemove: File) => {
    if (isImporting) return;

    setPendingFiles((currentFiles) =>
      currentFiles.filter(
        (file) =>
          file.name !== fileToRemove.name ||
          file.size !== fileToRemove.size ||
          file.lastModified !== fileToRemove.lastModified,
      ),
    );
  };

  const handleImport = async () => {
    if (!pendingFiles.length || isImporting) return;

    setIsImporting(true);
    setIsDragging(false);
    setImportResult(null);
    setError(null);

    try {
      const result = await importExport(pendingFiles);

      setImportResult(result);
      setPendingFiles([]);

      await refreshLibraryStats();
    } catch (error) {
      if (typeof error === "object" && error !== null && "error" in error) {
        const backendError = error as { error?: { message?: string } };

        setError(
          backendError.error?.message ??
            "Unable to import your Letterboxd data.",
        );
      } else {
        setError("Unable to import your Letterboxd data.");
      }
    } finally {
      setIsImporting(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (isImporting) return;
    addFiles(Array.from(event.target.files ?? []));
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!isImporting) setIsDragging(true);
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!isImporting) setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (isImporting) return;

    setIsDragging(false);
    addFiles(Array.from(event.dataTransfer.files));
  };

  const formatFileSize = (size: number) => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-6 pt-8">
        <section>
          <AppHeader
            title="Discover movies for you"
            description="Find movies based on your taste and improve your recommendations with your Letterboxd history."
          />

          {isLoadingLibraryStats ? (
            <div className="mt-5 -mb-5 border border-border bg-surface p-4">
              <div className="h-3 w-52 animate-pulse bg-border" />
              <div className="mt-3 h-4 w-72 animate-pulse bg-border" />
              <div className="mt-2 h-4 w-64 animate-pulse bg-border" />
            </div>
          ) : hasLibraryData === false ? (
            <div className="mt-6 -mb-5 border border-border bg-surface p-4">
              <p className="text-sm font-medium text-text-secondary">
                Improve your recommendations
              </p>

              <p className="mt-1 text-xs leading-relaxed text-text-muted">
                You can start discovering movies now, but your recommendations
                may be less personalized without your Letterboxd history. Import
                it to help us learn your taste.
              </p>
            </div>
          ) : (
            libraryStats &&
            libraryStats.rated_total > 0 && (
              <div className="mt-5 -mb-5 border border-border bg-surface p-4">
                <p className="text-sm font-medium text-text-secondary">
                  Movies used for your recommendations
                </p>

                <p className="mt-1 text-2xl font-semibold text-text">
                  {libraryStats.rated_with_embedding}
                  <span className="ml-2 text-sm font-normal text-text-muted">
                    of {libraryStats.rated_total} rated
                  </span>
                </p>

                  <p className="mt-2 text-xs leading-relaxed text-text-muted">
                    Not every movie you import can be used right away. Some may
                    not be recognized, and others are processed gradually, so
                    this number may grow over time.
                  </p>
              </div>
            )
          )}

          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <button
              type="button"
              onClick={handleCreateSession}
              disabled={isCreatingSession || isImporting}
              className={`group flex min-h-44 cursor-pointer flex-col border border-border bg-surface p-6 text-left disabled:cursor-auto disabled:opacity-60 disabled:border-border disabled:bg-surface ${
                !isImporting
                  ? "transition hover:border-primary hover:bg-surface-hover"
                  : ""
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex h-12 w-12 items-center justify-center">
                  <Heart
                    size={36}
                    strokeWidth={1.5}
                    className={`text-primary ${
                      !isImporting
                        ? "transition group-hover:scale-105"
                        : ""
                    }`}
                  />
                </div>

                <ArrowRight
                  size={21}
                  strokeWidth={1.8}
                  className={`text-text-muted ${
                    !isImporting
                      ? "transition group-hover:translate-x-1 group-hover:text-primary"
                      : ""
                  }`}
                />
              </div>

              <h2 className="mt-5 text-lg font-semibold">
                Create Swipe Session
              </h2>

              <p className="mt-2 text-sm leading-relaxed text-text-muted">
                Start discovering movies based on your taste.
              </p>

              <p className="mt-auto pt-5 text-sm font-medium text-primary">
                {isCreatingSession
                  ? "Starting session..."
                  : "Start discovering"}
              </p>
            </button>

            <div className="min-h-44 border border-border bg-surface p-6">
              <div className="flex items-start justify-between">
                <div className="flex h-12 w-12 items-center justify-center">
                  <Upload
                    size={36}
                    strokeWidth={1.5}
                    className="text-primary"
                  />
                </div>

                {pendingFiles.length > 0 && (
                  <span className="text-xs font-medium text-primary">
                    {pendingFiles.length}{" "}
                    {pendingFiles.length === 1 ? "file" : "files"}
                  </span>
                )}
              </div>

              <h2 className="mt-5 text-lg font-semibold">
                Import Letterboxd
              </h2>

              <p className="mt-2 text-sm leading-relaxed text-text-muted">
                Improve your recommendations using your Letterboxd history.
                <span className="mt-1 block text-xs text-text-muted/70">
                  First import can take up to several minutes, depending on size.
                </span>
              </p>

              <Link
                to="/instructions"
                className="mt-4 inline-flex cursor-pointer items-center gap-2 border border-border bg-surface-hover px-4 py-2
                          text-xs font-medium text-text transition hover:border-primary hover:text-primary"
              >
                Don't know how?
                <ArrowRight size={14} strokeWidth={1.8} />
              </Link>

              {pendingFiles.length > 0 && (
                <div className="mt-5 space-y-2">
                  {pendingFiles.map((file) => (
                    <div
                      key={`${file.name}-${file.size}-${file.lastModified}`}
                      className={`flex items-center gap-3 border border-border bg-background px-3 py-2 ${
                        isImporting ? "opacity-60" : ""
                      }`}
                    >
                      <FileText
                        size={17}
                        strokeWidth={1.6}
                        className="shrink-0 text-primary"
                      />

                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-text-secondary">
                          {file.name}
                        </p>

                        <p className="text-[11px] text-text-muted">
                          {formatFileSize(file.size)}
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          removeFile(file);
                        }}
                        disabled={isImporting}
                        className="shrink-0 cursor-pointer text-text-muted transition hover:text-red-400 disabled:cursor-auto disabled:opacity-40"
                        aria-label={`Remove ${file.name}`}
                      >
                        <Trash2 size={16} strokeWidth={1.6} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div
                onClick={() => {
                  if (!isImporting) fileInputRef.current?.click();
                }}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`mt-5 flex min-h-28 flex-col items-center justify-center border border-dashed px-4 py-5 text-center transition ${
                  isImporting
                    ? "cursor-auto border-border opacity-50"
                    : isDragging
                      ? "cursor-copy border-primary bg-surface-hover"
                      : "cursor-pointer border-border hover:border-primary hover:bg-surface-hover"
                }`}
              >
                <Upload
                  size={25}
                  strokeWidth={1.5}
                  className="text-primary"
                />

                <p className="mt-2 text-sm font-medium text-text-secondary">
                  {isImporting ? "Importing..." : "Drop files or browse"}
                </p>

                <p className="mt-1 text-xs text-text-muted">
                  ZIP export or individual CSV files
                </p>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".zip,.csv"
                  multiple
                  disabled={isImporting}
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>

              {pendingFiles.length > 0 && (
                <button
                  type="button"
                  onClick={handleImport}
                  disabled={isImporting}
                  className="mt-3 flex w-full cursor-pointer items-center justify-center gap-2 bg-primary px-4 py-2.5 text-sm font-semibold text-background transition hover:bg-primary-hover disabled:cursor-auto disabled:opacity-60"
                >
                  {isImporting ? (
                    "Importing..."
                  ) : (
                    <>
                      <Upload size={16} strokeWidth={1.8} />
                      Import files
                    </>
                  )}
                </button>
              )}
            </div>
          </div>

          {importResult && (
            <div className="mt-3 border border-border bg-surface p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center border border-primary">
                  <Check size={17} strokeWidth={2} className="text-primary" />
                </div>

                <div>
                  <h3 className="text-sm font-semibold">
                    Import completed
                  </h3>

                  <p className="mt-0.5 text-xs text-text-muted">
                    Your Letterboxd data has been processed.
                  </p>
                </div>
              </div>

              {importResult.missing.length > 0 && (
                <div className="mt-4 border-t border-border pt-4">
                  <p className="text-xs leading-relaxed text-text-muted">
                    <span className="font-medium text-text-secondary">
                      Missing files:
                    </span>{" "}
                    {importResult.missing.join(" | ")}
                  </p>

                  <p className="mt-2 text-xs leading-relaxed text-text-muted">
                    If possible, please import the missing files as well.
                    Having more information about your movie history helps
                    improve the accuracy of your recommendations.
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="mt-3 border border-border bg-surface px-5 py-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-sm font-medium text-text-secondary">
                  What can you import?
                </p>

                <ul className="mt-2 space-y-1 text-xs text-text-muted">
                  <li>• The complete Letterboxd ZIP export</li>
                  <li>• Individual CSV files from the export</li>
                </ul>
              </div>

              <div>
                <p className="text-sm font-medium text-text-secondary">
                  Supported files
                </p>

                <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-muted">
                  <span>ratings.csv</span>
                  <span className="text-border">|</span>
                  <span>diary.csv</span>
                  <span className="text-border">|</span>
                  <span>watched.csv</span>
                  <span className="text-border">|</span>
                  <span>likes/films.csv</span>
                  <span className="text-border">|</span>
                  <span>watchlist.csv</span>
                </div>
              </div>
            </div>

            <div className="mt-4 flex items-start gap-2 border-t border-border pt-4">
              <FileArchive
                size={16}
                strokeWidth={1.6}
                className="mt-0.5 shrink-0 text-primary"
              />

              <p className="text-xs leading-relaxed text-text-muted">
                Please do not modify the CSV files before importing them.
                Changes to their structure or contents may cause import errors.
              </p>
            </div>
          </div>

          {error && (
            <div className="mt-5 border border-border bg-surface p-4 text-sm text-red-400">
              {error}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}