import { useEffect, useRef, useState } from "react";

import {
  importExport,
  type ImportJobStatus,
  type ImportResult,
} from "../services/imports";
import { getErrorMessage } from "../utils/errors";

export const fileKey = (file: File) =>
  `${file.name}-${file.size}-${file.lastModified}`;

/** State and actions shared by every Letterboxd import UI. */
export function useLetterboxdImport(
  onImported?: (result: ImportResult) => void,
) {
  const inputRef = useRef<HTMLInputElement>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<ImportJobStatus | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // A file input that still holds its last selection won't fire `change`
  // when the same file is picked again.
  useEffect(() => {
    if (files.length === 0 && inputRef.current) {
      inputRef.current.value = "";
    }
  }, [files]);

  const addFiles = (incoming: File[]) => {
    if (!incoming.length || isImporting) return;

    setResult(null);
    setError(null);

    setFiles((current) => {
      const known = new Set(current.map(fileKey));

      return [...current, ...incoming.filter((file) => !known.has(fileKey(file)))];
    });
  };

  const replaceFiles = (next: File[]) => setFiles(next);

  const removeFile = (fileToRemove: File) => {
    if (isImporting) return;

    setFiles((current) =>
      current.filter((file) => fileKey(file) !== fileKey(fileToRemove)),
    );
  };

  const openFilePicker = () => {
    if (!isImporting) inputRef.current?.click();
  };

  const startImport = async () => {
    if (files.length === 0 || isImporting) return;

    setIsImporting(true);
    setResult(null);
    setError(null);

    try {
      const imported = await importExport(files, setStatus);

      setResult(imported);
      setFiles([]);
      onImported?.(imported);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsImporting(false);
      setStatus(null);
    }
  };

  return {
    inputRef,
    files,
    status,
    isImporting,
    result,
    error,
    addFiles,
    replaceFiles,
    removeFile,
    openFilePicker,
    startImport,
  };
}