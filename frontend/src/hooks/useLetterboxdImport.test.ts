import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  importExport,
  type ImportJobStatus,
  type ImportResult,
} from "../services/imports";
import { getErrorMessage } from "../utils/errors";
import { fileKey, useLetterboxdImport } from "./useLetterboxdImport";

vi.mock("../services/imports", () => ({
  importExport: vi.fn(),
}));

vi.mock("../utils/errors", () => ({
  getErrorMessage: vi.fn(),
}));

const mockedImportExport = vi.mocked(importExport);
const mockedGetErrorMessage = vi.mocked(getErrorMessage);

function createFile(
  name: string,
  content = "file content",
  lastModified = 1,
): File {
  return new File([content], name, {
    type: "text/csv",
    lastModified,
  });
}

function createImportResult(): ImportResult {
  return {} as ImportResult;
}

describe("fileKey", () => {
  it("creates a key from the file name, size, and last modified timestamp", () => {
    const file = createFile("diary.csv", "hello", 123);

    expect(fileKey(file)).toBe("diary.csv-5-123");
  });

  it("creates different keys for files with different names", () => {
    const first = createFile("first.csv", "same", 123);
    const second = createFile("second.csv", "same", 123);

    expect(fileKey(first)).not.toBe(fileKey(second));
  });

  it("creates different keys for files with different sizes", () => {
    const first = createFile("diary.csv", "one", 123);
    const second = createFile("diary.csv", "longer", 123);

    expect(fileKey(first)).not.toBe(fileKey(second));
  });

  it("creates different keys for files with different modification timestamps", () => {
    const first = createFile("diary.csv", "same", 123);
    const second = createFile("diary.csv", "same", 456);

    expect(fileKey(first)).not.toBe(fileKey(second));
  });
});

describe("useLetterboxdImport", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockedImportExport.mockResolvedValue(createImportResult());
    mockedGetErrorMessage.mockReturnValue("Import failed");
  });

  it("starts with an empty state", () => {
    const { result } = renderHook(() => useLetterboxdImport());

    expect(result.current.files).toEqual([]);
    expect(result.current.status).toBeNull();
    expect(result.current.isImporting).toBe(false);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.inputRef.current).toBeNull();
  });

  it("adds files to the selection", () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const firstFile = createFile("diary.csv");
    const secondFile = createFile("ratings.csv");

    act(() => {
      result.current.addFiles([firstFile, secondFile]);
    });

    expect(result.current.files).toEqual([firstFile, secondFile]);
  });

  it("ignores an empty incoming file list", () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");

    act(() => {
      result.current.addFiles([file]);
      result.current.addFiles([]);
    });

    expect(result.current.files).toEqual([file]);
  });

  it("does not add duplicate files", () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const originalFile = createFile("diary.csv", "content", 123);
    const duplicateFile = createFile("diary.csv", "content", 123);

    act(() => {
      result.current.addFiles([originalFile]);
      result.current.addFiles([duplicateFile]);
    });

    expect(result.current.files).toHaveLength(1);
    expect(result.current.files[0]).toBe(originalFile);
  });

  it("allows files with the same name when their keys differ", () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const firstFile = createFile("diary.csv", "short", 123);
    const secondFile = createFile("diary.csv", "different content", 123);

    act(() => {
      result.current.addFiles([firstFile, secondFile]);
    });

    expect(result.current.files).toEqual([firstFile, secondFile]);
  });

  it("clears the previous result and error when adding files", async () => {
    const importedResult = createImportResult();
    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");

    mockedImportExport.mockResolvedValueOnce(importedResult);

    act(() => {
      result.current.addFiles([file]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(result.current.result).toBe(importedResult);
    expect(result.current.files).toEqual([]);

    act(() => {
      result.current.addFiles([file]);
    });

    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.files).toEqual([file]);
  });

  it("replaces the selected files", () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const firstFile = createFile("first.csv");
    const secondFile = createFile("second.csv");

    act(() => {
      result.current.addFiles([firstFile]);
      result.current.replaceFiles([secondFile]);
    });

    expect(result.current.files).toEqual([secondFile]);
  });

  it("allows replacing the selection with an empty list", () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");

    act(() => {
      result.current.addFiles([file]);
      result.current.replaceFiles([]);
    });

    expect(result.current.files).toEqual([]);
  });

  it("removes a selected file", () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const firstFile = createFile("first.csv");
    const secondFile = createFile("second.csv");

    act(() => {
      result.current.addFiles([firstFile, secondFile]);
      result.current.removeFile(firstFile);
    });

    expect(result.current.files).toEqual([secondFile]);
  });

  it("removes files by file key rather than object identity", () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const selectedFile = createFile("diary.csv", "content", 123);
    const equivalentFile = createFile("diary.csv", "content", 123);

    act(() => {
      result.current.addFiles([selectedFile]);
      result.current.removeFile(equivalentFile);
    });

    expect(result.current.files).toEqual([]);
  });

  it("opens the file picker when a file input is attached", () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const click = vi.fn();
    const input = document.createElement("input");

    input.type = "file";
    input.click = click;

    act(() => {
      result.current.inputRef.current = input;
      result.current.openFilePicker();
    });

    expect(click).toHaveBeenCalledTimes(1);
  });

  it("does nothing when opening the file picker without an attached input", () => {
    const { result } = renderHook(() => useLetterboxdImport());

    expect(() => {
      act(() => {
        result.current.openFilePicker();
      });
    }).not.toThrow();
  });

  it("does not start an import when no files are selected", async () => {
    const { result } = renderHook(() => useLetterboxdImport());

    await act(async () => {
      await result.current.startImport();
    });

    expect(mockedImportExport).not.toHaveBeenCalled();
    expect(result.current.isImporting).toBe(false);
  });

  it("imports the selected files and stores the result", async () => {
    const importedResult = createImportResult();
    const { result } = renderHook(() => useLetterboxdImport());
    const firstFile = createFile("diary.csv");
    const secondFile = createFile("ratings.csv");

    mockedImportExport.mockResolvedValueOnce(importedResult);

    act(() => {
      result.current.addFiles([firstFile, secondFile]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(mockedImportExport).toHaveBeenCalledTimes(1);
    expect(mockedImportExport).toHaveBeenCalledWith(
      [firstFile, secondFile],
      expect.any(Function),
    );
    expect(result.current.result).toBe(importedResult);
    expect(result.current.files).toEqual([]);
    expect(result.current.error).toBeNull();
    expect(result.current.isImporting).toBe(false);
    expect(result.current.status).toBeNull();
  });

  it("passes the status setter to the import service", async () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");
    const status = {} as ImportJobStatus;

    mockedImportExport.mockImplementationOnce(async (_files, setStatus) => {
      setStatus?.(status);
      return createImportResult();
    });

    act(() => {
      result.current.addFiles([file]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(result.current.status).toBeNull();
  });

  it("calls the onImported callback after a successful import", async () => {
    const importedResult = createImportResult();
    const onImported = vi.fn<(value: ImportResult) => void>();
    const { result } = renderHook(() => useLetterboxdImport(onImported));
    const file = createFile("diary.csv");

    mockedImportExport.mockResolvedValueOnce(importedResult);

    act(() => {
      result.current.addFiles([file]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(onImported).toHaveBeenCalledTimes(1);
    expect(onImported).toHaveBeenCalledWith(importedResult);
  });

  it("does not call onImported when the import fails", async () => {
    const onImported = vi.fn<(value: ImportResult) => void>();
    const { result } = renderHook(() => useLetterboxdImport(onImported));
    const file = createFile("diary.csv");

    mockedImportExport.mockRejectedValueOnce(new Error("Service failure"));

    act(() => {
      result.current.addFiles([file]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(onImported).not.toHaveBeenCalled();
  });

  it("sets an error when the import fails", async () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");
    const importError = new Error("Service failure");

    mockedImportExport.mockRejectedValueOnce(importError);
    mockedGetErrorMessage.mockReturnValueOnce("Could not import files");

    act(() => {
      result.current.addFiles([file]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(mockedGetErrorMessage).toHaveBeenCalledWith(importError);
    expect(result.current.error).toBe("Could not import files");
    expect(result.current.files).toEqual([file]);
    expect(result.current.result).toBeNull();
    expect(result.current.isImporting).toBe(false);
    expect(result.current.status).toBeNull();
  });

  it("clears the error when adding new files after a failed import", async () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const firstFile = createFile("first.csv");
    const secondFile = createFile("second.csv");

    mockedImportExport.mockRejectedValueOnce(new Error("Service failure"));

    act(() => {
      result.current.addFiles([firstFile]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(result.current.error).toBe("Import failed");

    act(() => {
      result.current.addFiles([secondFile]);
    });

    expect(result.current.error).toBeNull();
    expect(result.current.files).toEqual([firstFile, secondFile]);
  });

  it("clears the status after a successful import", async () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");

    mockedImportExport.mockImplementationOnce(async (_files, setStatus) => {
      setStatus?.({} as ImportJobStatus);
      return createImportResult();
    });

    act(() => {
      result.current.addFiles([file]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(result.current.status).toBeNull();
  });

  it("clears the status after a failed import", async () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");

    mockedImportExport.mockImplementationOnce(async (_files, setStatus) => {
      setStatus?.({} as ImportJobStatus);
      throw new Error("Service failure");
    });

    act(() => {
      result.current.addFiles([file]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(result.current.status).toBeNull();
    expect(result.current.isImporting).toBe(false);
  });

  it("prevents starting another import while one is in progress", async () => {
    let resolveImport!: (value: ImportResult) => void;

    mockedImportExport.mockReturnValueOnce(
      new Promise<ImportResult>((resolve) => {
        resolveImport = resolve;
      }),
    );

    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");

    act(() => {
      result.current.addFiles([file]);
    });

    let firstImport!: Promise<void>;

    act(() => {
      firstImport = result.current.startImport();
    });

    await waitFor(() => {
      expect(result.current.isImporting).toBe(true);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(mockedImportExport).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveImport(createImportResult());
      await firstImport;
    });

    expect(result.current.isImporting).toBe(false);
  });

  it("ignores files added while an import is in progress", async () => {
    let resolveImport!: (value: ImportResult) => void;

    mockedImportExport.mockReturnValueOnce(
      new Promise<ImportResult>((resolve) => {
        resolveImport = resolve;
      }),
    );

    const { result } = renderHook(() => useLetterboxdImport());
    const firstFile = createFile("first.csv");
    const secondFile = createFile("second.csv");

    act(() => {
      result.current.addFiles([firstFile]);
    });

    let importPromise!: Promise<void>;

    act(() => {
      importPromise = result.current.startImport();
    });

    await waitFor(() => {
      expect(result.current.isImporting).toBe(true);
    });

    act(() => {
      result.current.addFiles([secondFile]);
    });

    expect(result.current.files).toEqual([firstFile]);

    await act(async () => {
      resolveImport(createImportResult());
      await importPromise;
    });

    expect(result.current.files).toEqual([]);
  });

  it("prevents removing files while an import is in progress", async () => {
    let resolveImport!: (value: ImportResult) => void;

    mockedImportExport.mockReturnValueOnce(
      new Promise<ImportResult>((resolve) => {
        resolveImport = resolve;
      }),
    );

    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");

    act(() => {
      result.current.addFiles([file]);
    });

    let importPromise!: Promise<void>;

    act(() => {
      importPromise = result.current.startImport();
    });

    await waitFor(() => {
      expect(result.current.isImporting).toBe(true);
    });

    act(() => {
      result.current.removeFile(file);
    });

    expect(result.current.files).toEqual([file]);

    await act(async () => {
      resolveImport(createImportResult());
      await importPromise;
    });
  });

  it("does not open the file picker while an import is in progress", async () => {
    let resolveImport!: (value: ImportResult) => void;

    mockedImportExport.mockReturnValueOnce(
      new Promise<ImportResult>((resolve) => {
        resolveImport = resolve;
      }),
    );

    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");
    const click = vi.fn();
    const input = document.createElement("input");

    input.type = "file";
    input.click = click;

    act(() => {
      result.current.inputRef.current = input;
      result.current.addFiles([file]);
    });

    let importPromise!: Promise<void>;

    act(() => {
      importPromise = result.current.startImport();
    });

    await waitFor(() => {
      expect(result.current.isImporting).toBe(true);
    });

    act(() => {
      result.current.openFilePicker();
    });

    expect(click).not.toHaveBeenCalled();

    await act(async () => {
      resolveImport(createImportResult());
      await importPromise;
    });
  });

  it("clears the file input value when the selected files become empty", async () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const input = document.createElement("input");

    input.type = "file";

    act(() => {
      result.current.inputRef.current = input;
      result.current.addFiles([createFile("diary.csv")]);
    });

    await waitFor(() => {
      expect(result.current.files).toHaveLength(1);
    });

    act(() => {
      result.current.replaceFiles([]);
    });

    await waitFor(() => {
      expect(input.value).toBe("");
    });
  });

  it("supports using the hook without an onImported callback", async () => {
    const { result } = renderHook(() => useLetterboxdImport());
    const file = createFile("diary.csv");

    act(() => {
      result.current.addFiles([file]);
    });

    await act(async () => {
      await result.current.startImport();
    });

    expect(result.current.result).not.toBeNull();
    expect(result.current.error).toBeNull();
  });
});