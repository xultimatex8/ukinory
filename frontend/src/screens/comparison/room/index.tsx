import { useEffect, useRef, useState } from "react";
import {
  Check,
  Clock,
  FileArchive,
  FileText,
  Loader2,
  LogOut,
  Trash2,
  Upload,
} from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import LeaveRoomModal from "../../../components/LeaveRoomModal";
import ErrorScreen from "../../../components/ErrorScreen";
import { getCurrentUser, type User } from "../../../services/user";
import {
  leaveRoom,
  type Invite,
} from "../../../services/comparisons";
import { useComparisonRoom } from "../../../hooks/useComparisonRoom";
import InviteSharePanel from "../../../components/InviteSharePanel";
import { importExport, type ImportResult } from "../../../services/imports";
import ComparisonResultView from "../../../components/ComparisonResultView";

function StatusRow({
  label,
  joined,
  hasData,
}: {
  label: string;
  joined: boolean;
  hasData: boolean | null;
}) {
  let text = "Hasn't joined yet";
  let done = false;

  if (joined && hasData) {
    text = "Joined · data imported";
    done = true;
  } else if (joined && hasData === false) {
    text = "Joined · needs to import their data";
  } else if (joined) {
    text = "Joined";
    done = true;
  }

  return (
    <li className="flex items-center justify-between gap-4 px-4 py-3 text-sm">
      <span className="text-text">{label}</span>
      <span
        className={`inline-flex items-center gap-1.5 text-xs ${
          done ? "text-emerald-400" : "text-text-muted"
        }`}
      >
        {done ? <Check size={14} /> : <Clock size={14} />}
        {text}
      </span>
    </li>
  );
}

function Waiting({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex flex-col items-center border border-border bg-surface px-6 py-12 text-center">
      <Loader2 size={26} className="animate-spin text-primary" />
      <h2 className="mt-4 text-lg font-semibold">{title}</h2>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-text-muted">
        {text}
      </p>
    </div>
  );
}

function ImportSection({ onImported }: { onImported: () => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [isImporting, setIsImporting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

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

      onImported();
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

    if (!isImporting) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();

    if (!isImporting) {
      setIsDragging(false);
    }
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
    <div className="border border-border bg-surface p-6">
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
        Import your Letterboxd history so your movie taste can be
        compared with your friend's.
        <span className="mt-1 block text-xs text-text-muted/70">
          First import can take up to several minutes, depending on
          size.
        </span>
      </p>

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
          if (!isImporting) {
            fileInputRef.current?.click();
          }
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

      {importResult && (
        <div className="mt-3 border border-border bg-surface p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center border border-primary">
              <Check
                size={17}
                strokeWidth={2}
                className="text-primary"
              />
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
                improve the accuracy of your comparison.
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
    </div>
  );
}

export default function ComparisonRoomScreen() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const initialInvite =
    (location.state as { invite?: Invite } | null)?.invite ?? null;

  const {
    room,
    result,
    phase,
    error,
    fatal,
    isGenerating,
    refresh,
    reload,
    retryGeneration,
  } = useComparisonRoom(id);

  const [me, setMe] = useState<User | null>(null);
  const [meChecked, setMeChecked] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);
  const [isLeaveModalOpen, setIsLeaveModalOpen] = useState(false);
  const [leaveError, setLeaveError] = useState<string | null>(null);

  const handleLeave = async () => {
    if (!id || isLeaving) return;

    setIsLeaving(true);
    setLeaveError(null);

    try {
      await leaveRoom(id);
      navigate("/");
    } catch {
      setIsLeaving(false);
      setLeaveError("Unable to leave the room. Please try again.");
    }
  };

  const handleConfirmLeave = () => {
    if (isLeaving) return;

    void handleLeave();
  };

  useEffect(() => {
    if (!result) return;

    let cancelled = false;

    getCurrentUser()
      .then((user) => {
        if (!cancelled) setMe(user);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setMeChecked(true);
      });

    return () => {
      cancelled = true;
    };
  }, [result]);

  if (fatal === "not_found") {
    return (
      <ErrorScreen
        message="This room doesn't exist or is no longer available."
        buttonText="Back to home"
      />
    );
  }

  if (fatal === "forbidden") {
    return (
      <ErrorScreen
        message="You're not part of this room."
        buttonText="Back to home"
      />
    );
  }

  if (fatal === "closed") {
    return (
      <ErrorScreen
        message="This comparison room is closed."
        buttonText="Back to home"
      />
    );
  }

  if (error) {
    return <ErrorScreen message={error} onRetry={reload} />;
  }

  const showStatus =
    room !== null &&
    phase !== "ready" &&
    phase !== "waiting_partner";

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto flex w-full max-w-7xl flex-col px-4 py-6 sm:px-6 sm:py-10">
        {room && room.status !== "FINISHED" && (
          <div className="mb-2 flex justify-end">
            <button
              type="button"
              onClick={() => {
                setLeaveError(null);
                setIsLeaveModalOpen(true);
              }}
              disabled={isLeaving}
              className="flex cursor-pointer items-center gap-2 border border-border bg-surface px-4 py-2 text-xs font-medium text-text-muted transition hover:bg-surface-hover hover:text-text disabled:cursor-auto disabled:opacity-50"
            >
              <LogOut size={14} strokeWidth={1.7} />
              Leave room
            </button>
          </div>
        )}

        {phase === "loading" && (
          <Waiting
            title="Opening the room…"
            text="Just a moment."
          />
        )}

        {phase === "waiting_partner" && (
          <div className="space-y-5">
            <div>
              <h1 className="text-2xl font-bold">
                Waiting for your friend
              </h1>

              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                Send them the link or the code. This page updates by
                itself as soon as they join.
              </p>
            </div>

            <InviteSharePanel
              roomId={id!}
              initialInvite={initialInvite}
            />

            {room && !room.you_have_data && (
              <div>
                <h2 className="text-lg font-semibold">
                  Import your data while you wait
                </h2>

                <div className="mt-3">
                  <ImportSection
                    onImported={() => void refresh()}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {showStatus && room && (
          <ul className="mb-6 divide-y divide-border border border-border bg-surface">
            <StatusRow
              label="You"
              joined
              hasData={room.you_have_data}
            />

            <StatusRow
              label="Your friend"
              joined={room.partner_joined}
              hasData={room.partner_has_data}
            />
          </ul>
        )}

        {phase === "needs_import" && (
          <div className="space-y-4">
            <div>
              <h1 className="text-2xl font-bold">
                Import your Letterboxd data
              </h1>

              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                Your friend is in the room. We need your export to
                compare tastes — the comparison starts as soon as the
                import finishes.
              </p>
            </div>

            <ImportSection
              onImported={() => void refresh()}
            />
          </div>
        )}

        {phase === "waiting_partner_data" && (
          <Waiting
            title="Waiting for your friend's data"
            text="They still need to import their Letterboxd export. The comparison starts automatically once they do."
          />
        )}

        {phase === "generating" && (
          <Waiting
            title="Comparing your tastes…"
            text="This usually takes a few seconds."
          />
        )}

        {phase === "failed" && (
          <div className="border border-border bg-surface px-6 py-10 text-center">
            <h2 className="text-lg font-semibold">
              Something went wrong comparing your tastes
            </h2>

            <p className="mt-2 text-sm text-text-muted">
              Your data is safe. Try again in a moment.
            </p>

            <button
              type="button"
              disabled={isGenerating}
              onClick={retryGeneration}
              className="mt-5 inline-flex cursor-pointer items-center gap-2 border border-primary px-5 py-2.5 text-sm font-medium text-primary transition hover:bg-primary hover:text-background disabled:cursor-auto disabled:opacity-40"
            >
              {isGenerating && (
                <Loader2
                  size={15}
                  className="animate-spin"
                />
              )}

              Try again
            </button>
          </div>
        )}

        {phase === "ready" && result && !meChecked && (
          <Waiting
            title="Almost there…"
            text="Loading your results."
          />
        )}

        {phase === "ready" && result && meChecked && (
          <div>
            <h1 className="mb-6 text-2xl font-bold">
              Your taste comparison
            </h1>

            <ComparisonResultView
              result={result}
              currentUserId={me?.id ?? null}
            />
          </div>
        )}
      </div>

      {isLeaveModalOpen && (
        <LeaveRoomModal
          isLeaving={isLeaving}
          error={leaveError}
          onClose={() => setIsLeaveModalOpen(false)}
          onLeave={handleConfirmLeave}
        />
      )}
    </main>
  );
}