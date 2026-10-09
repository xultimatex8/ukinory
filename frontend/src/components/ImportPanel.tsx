import { useRef, useState } from "react";
import { Check, Loader2, Upload } from "lucide-react";

import { importExport, type ImportResult } from "../services/imports";
import { getErrorMessage } from "../utils/errors";

interface ImportPanelProps {
  onImported?: (result: ImportResult) => void;
}

const STATUS_LABELS: Record<string, string> = {
  pending: "Queued — waiting for a free worker…",
  running: "Processing your export…",
};

export default function ImportPanel({ onImported }: ImportPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  const handleImport = async () => {
    if (files.length === 0 || isImporting) return;

    setIsImporting(true);
    setError(null);
    setResult(null);

    try {
      const imported = await importExport(files, setStatus);
      setResult(imported);
      setFiles([]);
      if (inputRef.current) inputRef.current.value = "";
      onImported?.(imported);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsImporting(false);
      setStatus(null);
    }
  };

  return (
    <div className="border border-border bg-surface p-5">
      <p className="text-sm leading-relaxed text-text-secondary">
        Upload the export from your Letterboxd account (Settings → Import &amp;
        Export → Export your data). You can send the .zip or the individual
        .csv files.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".zip,.csv"
        multiple
        disabled={isImporting}
        onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
        className="hidden"
      />

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <button
          type="button"
          disabled={isImporting}
          onClick={() => inputRef.current?.click()}
          className="flex cursor-pointer items-center justify-center gap-2 border border-border bg-background px-4 py-2.5 text-sm font-medium text-text-secondary transition hover:border-primary hover:text-primary disabled:cursor-auto disabled:opacity-40"
        >
          <Upload size={15} />
          {files.length === 0 ? "Choose files" : "Change files"}
        </button>

        <button
          type="button"
          disabled={files.length === 0 || isImporting}
          onClick={() => void handleImport()}
          className="flex cursor-pointer items-center justify-center gap-2 border border-primary bg-primary px-4 py-2.5 text-sm font-medium text-background transition hover:opacity-90 disabled:cursor-auto disabled:opacity-40"
        >
          {isImporting && <Loader2 size={15} className="animate-spin" />}
          {isImporting ? "Importing…" : "Import"}
        </button>
      </div>

      {files.length > 0 && !isImporting && (
        <p className="mt-3 truncate text-xs text-text-muted">
          {files.length === 1
            ? files[0].name
            : `${files.length} files selected`}
        </p>
      )}

      {isImporting && (
        <p className="mt-3 text-xs leading-relaxed text-text-muted">
          {(status && STATUS_LABELS[status]) ?? "Starting import…"} This can
          take a few minutes; you can keep this tab open.
        </p>
      )}

      {result && (
        <p className="mt-3 flex items-start gap-2 text-sm text-emerald-400">
          <Check size={16} className="mt-0.5 shrink-0" />
          <span>
            Import finished.
            {result.missing.length > 0 &&
              ` ${result.missing.length} title(s) couldn't be matched and were skipped.`}
          </span>
        </p>
      )}

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
    </div>
  );
}