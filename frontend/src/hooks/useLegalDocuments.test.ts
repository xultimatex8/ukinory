import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getCurrentLegalDocuments,
  type LegalDocument,
} from "../services/legal";
import { useLegalDocuments } from "./useLegalDocuments";

vi.mock("../services/legal", () => ({
  getCurrentLegalDocuments: vi.fn(),
}));

const mockedGetCurrentLegalDocuments = vi.mocked(
  getCurrentLegalDocuments,
);

function makeLegalDocument(
  overrides: Partial<LegalDocument> = {},
): LegalDocument {
  return {
    type: "TERMS",
    version: "1.0",
    ...overrides,
  } as LegalDocument;
}

describe("useLegalDocuments", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetCurrentLegalDocuments.mockResolvedValue([
      makeLegalDocument(),
    ]);
  });

  it("loads legal documents on mount", async () => {
    const documents = [
      makeLegalDocument(),
      makeLegalDocument({
        type: "PRIVACY",
        version: "2.0",
      }),
    ];

    mockedGetCurrentLegalDocuments.mockResolvedValue(documents);

    const { result } = renderHook(() => useLegalDocuments());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.documents).toBeNull();
    expect(result.current.error).toBeNull();

    await waitFor(() => {
      expect(result.current.documents).toEqual(documents);
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeNull();
    expect(mockedGetCurrentLegalDocuments).toHaveBeenCalledTimes(1);
  });

  it("sets an error when the initial request fails", async () => {
    mockedGetCurrentLegalDocuments.mockRejectedValue(
      new Error("Network failure"),
    );

    const { result } = renderHook(() => useLegalDocuments());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe(
        "Unable to load the Terms and Conditions and Privacy Policy.",
      );
    });

    expect(result.current.documents).toBeNull();
  });

  it("sets an error when the initial request returns no documents", async () => {
    mockedGetCurrentLegalDocuments.mockResolvedValue([]);

    const { result } = renderHook(() => useLegalDocuments());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe(
        "Unable to load the Terms and Conditions and Privacy Policy.",
      );
    });

    expect(result.current.documents).toBeNull();
  });

  it("reloads legal documents successfully", async () => {
    const initialDocuments = [makeLegalDocument()];
    const refreshedDocuments = [
      makeLegalDocument({ version: "2.0" }),
    ];

    mockedGetCurrentLegalDocuments
      .mockResolvedValueOnce(initialDocuments)
      .mockResolvedValueOnce(refreshedDocuments);

    const { result } = renderHook(() => useLegalDocuments());

    await waitFor(() => {
      expect(result.current.documents).toEqual(initialDocuments);
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.documents).toEqual(refreshedDocuments);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockedGetCurrentLegalDocuments).toHaveBeenCalledTimes(2);
  });

  it("sets an error when reloading fails", async () => {
    mockedGetCurrentLegalDocuments
      .mockResolvedValueOnce([makeLegalDocument()])
      .mockRejectedValueOnce(new Error("Network failure"));

    const { result } = renderHook(() => useLegalDocuments());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.documents).not.toBeNull();
    });

    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBe(
      "Unable to load the Terms and Conditions and Privacy Policy.",
    );
  });

  it("sets an error when reloading returns no documents", async () => {
    mockedGetCurrentLegalDocuments
      .mockResolvedValueOnce([makeLegalDocument()])
      .mockResolvedValueOnce([]);

    const { result } = renderHook(() => useLegalDocuments());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.documents).not.toBeNull();
    });

    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.error).toBe(
      "Unable to load the Terms and Conditions and Privacy Policy.",
    );
    expect(result.current.isLoading).toBe(false);
  });

  it("clears a previous error when reloading successfully", async () => {
    mockedGetCurrentLegalDocuments
      .mockRejectedValueOnce(new Error("Initial failure"))
      .mockResolvedValueOnce([makeLegalDocument()]);

    const { result } = renderHook(() => useLegalDocuments());

    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });

    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.documents).toEqual([makeLegalDocument()]);
    expect(result.current.isLoading).toBe(false);
  });

  it("keeps existing documents when a reload fails", async () => {
    const existingDocuments = [makeLegalDocument()];

    mockedGetCurrentLegalDocuments
      .mockResolvedValueOnce(existingDocuments)
      .mockRejectedValueOnce(new Error("Reload failed"));

    const { result } = renderHook(() => useLegalDocuments());

    await waitFor(() => {
      expect(result.current.documents).toEqual(existingDocuments);
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.documents).toEqual(existingDocuments);
    expect(result.current.error).toBe(
      "Unable to load the Terms and Conditions and Privacy Policy.",
    );
    expect(result.current.isLoading).toBe(false);
  });

  it("does not update state when the initial request resolves after unmount", async () => {
    let resolveDocuments!: (documents: LegalDocument[]) => void;

    mockedGetCurrentLegalDocuments.mockReturnValue(
      new Promise<LegalDocument[]>((resolve) => {
        resolveDocuments = resolve;
      }),
    );

    const { result, unmount } = renderHook(() => useLegalDocuments());

    unmount();

    await act(async () => {
      resolveDocuments([makeLegalDocument()]);
      await Promise.resolve();
    });

    expect(result.current.documents).toBeNull();
    expect(result.current.isLoading).toBe(true);
  });

  it("does not update state when the initial request rejects after unmount", async () => {
    let rejectDocuments!: (error: Error) => void;

    mockedGetCurrentLegalDocuments.mockReturnValue(
      new Promise<LegalDocument[]>((_, reject) => {
        rejectDocuments = reject;
      }),
    );

    const { result, unmount } = renderHook(() => useLegalDocuments());

    unmount();

    await act(async () => {
      rejectDocuments(new Error("Network failure"));
      await Promise.resolve();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.isLoading).toBe(true);
  });

  it("keeps the reload callback stable between renders", async () => {
    const { result } = renderHook(() => useLegalDocuments());

    const initialReload = result.current.reload;

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.reload).toBe(initialReload);
  });
});