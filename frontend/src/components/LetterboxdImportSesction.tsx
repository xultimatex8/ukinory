import { useState } from "react";
import { Check, FileArchive, FileText, Trash2, Upload } from "lucide-react";

import { fileKey, useLetterboxdImport } from "../hooks/useLetterboxdImport";

type ImportPurpose = "recommendations" | "comparison";

const COPY: Record<ImportPurpose, { intro: string; accuracyOf: string }> = {
  recommendations: {
    intro:
      "Import your Letterboxd history so we can pick movies that fit both of your tastes.",
    accuracyOf: "recommendations",
  },
  comparison: {
    intro:
      "Import your Letterboxd history so your movie taste can be compared with your friend's.",
    accuracyOf: "comparison",
  },
};

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

interface LetterboxdImportSectionProps {
  purpose: ImportPurpose;
  onImported: () => void;
}

export default function LetterboxdImportSection({
  purpose,
  onImported,
}: LetterboxdImportSectionProps) {
  const [isDragging, setIsDragging] = useState(false);

  const {
    inputRef,
    files,
    isImporting,
    result,
    error,
    addFiles,
    removeFile,
    openFilePicker,
    startImport,
  } = useLetterboxdImport(onImported);

  const copy = COPY[purpose];

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
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

  return (
    <div className="border border-border bg-surface p-6">
      <div className="flex items-start justify-between">
        <div className="flex h-12 w-12 items-center justify-center">
          <Upload size={36} strokeWidth={1.5} className="text-primary" />
        </div>

        {files.length > 0 && (
          <span className="text-xs font-medium text-primary">
            {files.length} {files.length === 1 ? "file" : "files"}
          </span>
        )}
      </div>

      <h2 className="mt-5 text-lg font-semibold">Import Letterboxd</h2>

      <p className="mt-2 text-sm leading-relaxed text-text-muted">
        {copy.intro}
        <span className="mt-1 block text-xs text-text-muted/70">
          First import can take up to several minutes, depending on size.
        </span>
      </p>

      {files.length > 0 && (
        <div className="mt-5 space-y-2">
          {files.map((file) => (
            <div
              key={fileKey(file)}
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
        onClick={openFilePicker}
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
        <Upload size={25} strokeWidth={1.5} className="text-primary" />

        <p className="mt-2 text-sm font-medium text-text-secondary">
          {isImporting ? "Importing..." : "Drop files or browse"}
        </p>

        <p className="mt-1 text-xs text-text-muted">
          ZIP export or individual CSV files
        </p>

        <input
          ref={inputRef}
          type="file"
          accept=".zip,.csv"
          multiple
          disabled={isImporting}
          onChange={handleFileChange}
          className="hidden"
        />
      </div>

      {files.length > 0 && (
        <button
          type="button"
          onClick={() => void startImport()}
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

      {result && (
        <div className="mt-3 border border-border bg-surface p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center border border-primary">
              <Check size={17} strokeWidth={2} className="text-primary" />
            </div>

            <div>
              <h3 className="text-sm font-semibold">Import completed</h3>

              <p className="mt-0.5 text-xs text-text-muted">
                Your Letterboxd data has been processed.
              </p>
            </div>
          </div>

          {result.missing.length > 0 && (
            <div className="mt-4 border-t border-border pt-4">
              <p className="text-xs leading-relaxed text-text-muted">
                <span className="font-medium text-text-secondary">
                  Missing files:
                </span>{" "}
                {result.missing.join(" | ")}
              </p>

              <p className="mt-2 text-xs leading-relaxed text-text-muted">
                If possible, please import the missing files as well. Having
                more information about your movie history helps improve the
                accuracy of your {copy.accuracyOf}.
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
            Please do not modify the CSV files before importing them. Changes
            to their structure or contents may cause import errors.
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