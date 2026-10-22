import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
  act,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import "@testing-library/jest-dom/vitest";

import DiscoverScreen from "./index";
import { importExport, type ImportResult } from "../../../services/imports";
import { getLibraryStats, type LibraryStats } from "../../../services/library";
import {
  createIndividualSwipeSession,
  startSwipeSession,
} from "../../../services/swipeSessions";

const { mockNavigate } = vi.hoisted(() => ({ mockNavigate: vi.fn() }));

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../../../components/LogoHeader", () => ({
  default: ({
    title,
    description,
  }: {
    title: string;
    description: string;
  }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  ),
}));

vi.mock("../../../services/imports", () => ({
  importExport: vi.fn(),
}));

vi.mock("../../../services/library", () => ({
  getLibraryStats: vi.fn(),
}));

vi.mock("../../../services/swipeSessions", () => ({
  createIndividualSwipeSession: vi.fn(),
  startSwipeSession: vi.fn(),
}));

const mockedImportExport = vi.mocked(importExport);
const mockedGetLibraryStats = vi.mocked(getLibraryStats);
const mockedCreateSession = vi.mocked(createIndividualSwipeSession);
const mockedStartSession = vi.mocked(startSwipeSession);

const createStats = (overrides: Partial<LibraryStats> = {}): LibraryStats =>
  ({
    rated_total: 0,
    rated_with_embedding: 0,
    ...overrides,
  }) as LibraryStats;

const createImportResult = (
  overrides: Partial<ImportResult> = {},
): ImportResult =>
  ({
    missing: [],
    ...overrides,
  }) as ImportResult;

const createFile = (
  name: string,
  { size, lastModified = 1 }: { size?: number; lastModified?: number } = {},
) => {
  const file = new File(["content"], name, {
    type: "text/csv",
    lastModified,
  });

  if (size !== undefined) {
    Object.defineProperty(file, "size", { value: size });
  }

  return file;
};

const renderScreen = async () => {
  const utils = render(
    <MemoryRouter>
      <DiscoverScreen />
    </MemoryRouter>,
  );

  // The screen waits at least 350ms before hiding the stats skeleton.
  await waitFor(() => {
    expect(utils.container.querySelector(".animate-pulse")).toBeNull();
  });

  return utils;
};

const getFileInput = (container: HTMLElement) =>
  container.querySelector('input[type="file"]') as HTMLInputElement;

const getDropzone = () =>
  screen.getByRole("button", { name: /Drop files or browse/i });

const addFilesViaInput = (container: HTMLElement, files: File[]) => {
  fireEvent.change(getFileInput(container), { target: { files } });
};

describe("DiscoverScreen", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();

    mockedGetLibraryStats.mockResolvedValue(createStats());
  });

  describe("layout", () => {
    it("renders the header, the main cards and the help section", async () => {
      await renderScreen();

      expect(
        screen.getByRole("heading", { name: "Discover movies for you" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "Create Swipe Session" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "Import Letterboxd" }),
      ).toBeInTheDocument();
      expect(screen.getByText("What can you import?")).toBeInTheDocument();
      expect(screen.getByText("Supported files")).toBeInTheDocument();
      expect(screen.getByText("ratings.csv")).toBeInTheDocument();
      expect(screen.getByText("watchlist.csv")).toBeInTheDocument();
    });

    it("renders the navigation links", async () => {
      await renderScreen();

      expect(
        screen.getByRole("link", { name: /Back to home/i }),
      ).toHaveAttribute("href", "/");
      expect(
        screen.getByRole("link", { name: /Don't know how\?/i }),
      ).toHaveAttribute("href", "/instructions");
    });

    it("restricts the file input to zip and csv files", async () => {
      const { container } = await renderScreen();

      const input = getFileInput(container);

      expect(input).toHaveAttribute("accept", ".zip,.csv");
      expect(input).toHaveAttribute("multiple");
    });

    it("does not render the import button or the error without pending files", async () => {
      await renderScreen();

      expect(
        screen.queryByRole("button", { name: /Import files/i }),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Import completed")).not.toBeInTheDocument();
    });
  });

  describe("library stats", () => {
    it("renders a skeleton while the stats are loading", () => {
      mockedGetLibraryStats.mockReturnValue(new Promise(() => {}));

      const { container } = render(
        <MemoryRouter>
          <DiscoverScreen />
        </MemoryRouter>,
      );

      expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
      expect(mockedGetLibraryStats).toHaveBeenCalledTimes(1);
    });

    it("suggests importing the history when there are no rated movies", async () => {
      mockedGetLibraryStats.mockResolvedValue(
        createStats({ rated_total: 0 }),
      );

      await renderScreen();

      expect(
        screen.getByText("Improve your recommendations"),
      ).toBeInTheDocument();
      expect(
        screen.queryByText("Movies used for your recommendations"),
      ).not.toBeInTheDocument();
    });

    it("renders the stats when there are rated movies", async () => {
      mockedGetLibraryStats.mockResolvedValue(
        createStats({ rated_total: 120, rated_with_embedding: 87 }),
      );

      await renderScreen();

      expect(
        screen.getByText("Movies used for your recommendations"),
      ).toBeInTheDocument();
      expect(screen.getByText("87")).toBeInTheDocument();
      expect(screen.getByText("of 120 rated")).toBeInTheDocument();
      expect(
        screen.queryByText("Improve your recommendations"),
      ).not.toBeInTheDocument();
    });

    it("renders neither message when the stats fail to load", async () => {
      mockedGetLibraryStats.mockRejectedValue(new Error("Request failed"));

      const { container } = await renderScreen();

      expect(container.querySelector(".animate-pulse")).toBeNull();
      expect(
        screen.queryByText("Improve your recommendations"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText("Movies used for your recommendations"),
      ).not.toBeInTheDocument();
    });
  });

  describe("creating a session", () => {
    it("creates and starts the session and navigates to it", async () => {
      mockedCreateSession.mockResolvedValue({ id: "session-1" } as never);
      mockedStartSession.mockResolvedValue(undefined as never);

      await renderScreen();

      fireEvent.click(
        screen.getByRole("button", { name: /Create Swipe Session/i }),
      );

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/discover/session-1");
      });

      expect(mockedCreateSession).toHaveBeenCalledTimes(1);
      expect(mockedStartSession).toHaveBeenCalledWith("session-1");
    });

    it("shows a loading label and disables the button while creating", async () => {
      mockedCreateSession.mockReturnValue(new Promise(() => {}));

      await renderScreen();

      const button = screen.getByRole("button", {
        name: /Create Swipe Session/i,
      });

      fireEvent.click(button);

      expect(
        await screen.findByText("Starting session..."),
      ).toBeInTheDocument();
      expect(button).toBeDisabled();
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it("renders an error and does not navigate when creating the session fails", async () => {
      mockedCreateSession.mockRejectedValue(new Error("Request failed"));

      await renderScreen();

      fireEvent.click(
        screen.getByRole("button", { name: /Create Swipe Session/i }),
      );

      expect(
        await screen.findByText("Unable to start a swipe session."),
      ).toBeInTheDocument();
      expect(mockNavigate).not.toHaveBeenCalled();
      expect(mockedStartSession).not.toHaveBeenCalled();
      expect(screen.getByText("Start discovering")).toBeInTheDocument();
    });

    it("renders an error when starting the session fails", async () => {
      mockedCreateSession.mockResolvedValue({ id: "session-1" } as never);
      mockedStartSession.mockRejectedValue(new Error("Request failed"));

      await renderScreen();

      fireEvent.click(
        screen.getByRole("button", { name: /Create Swipe Session/i }),
      );

      expect(
        await screen.findByText("Unable to start a swipe session."),
      ).toBeInTheDocument();
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it("clears a previous error when trying again", async () => {
      mockedCreateSession
        .mockRejectedValueOnce(new Error("Request failed"))
        .mockReturnValueOnce(new Promise(() => {}));

      await renderScreen();

      const button = screen.getByRole("button", {
        name: /Create Swipe Session/i,
      });

      fireEvent.click(button);

      expect(
        await screen.findByText("Unable to start a swipe session."),
      ).toBeInTheDocument();

      fireEvent.click(button);

      await waitFor(() => {
        expect(
          screen.queryByText("Unable to start a swipe session."),
        ).not.toBeInTheDocument();
      });
    });
  });

  describe("selecting files", () => {
    it("lists a selected file with its name and size", async () => {
      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("ratings.csv", { size: 500 })]);

      expect(screen.getAllByText("ratings.csv")).toHaveLength(2); // pending + supported list
      expect(screen.getByText("500 B")).toBeInTheDocument();
      expect(screen.getByText("1 file")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Import files" }),
      ).toBeInTheDocument();
    });

    it("uses the plural label with several files", async () => {
      const { container } = await renderScreen();

      addFilesViaInput(container, [
        createFile("a.csv", { lastModified: 1 }),
        createFile("b.csv", { lastModified: 2 }),
      ]);

      expect(screen.getByText("2 files")).toBeInTheDocument();
    });

    it("formats sizes in B, KB and MB", async () => {
      const { container } = await renderScreen();

      addFilesViaInput(container, [
        createFile("small.csv", { size: 1023, lastModified: 1 }),
        createFile("medium.csv", { size: 2048, lastModified: 2 }),
        createFile("large.csv", { size: 3 * 1024 * 1024, lastModified: 3 }),
      ]);

      expect(screen.getByText("1023 B")).toBeInTheDocument();
      expect(screen.getByText("2.0 KB")).toBeInTheDocument();
      expect(screen.getByText("3.0 MB")).toBeInTheDocument();
    });

    it("accumulates files across several selections", async () => {
      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv", { lastModified: 1 })]);
      addFilesViaInput(container, [createFile("b.csv", { lastModified: 2 })]);

      expect(screen.getByText("a.csv")).toBeInTheDocument();
      expect(screen.getByText("b.csv")).toBeInTheDocument();
      expect(screen.getByText("2 files")).toBeInTheDocument();
    });

    it("ignores duplicated files", async () => {
      const { container } = await renderScreen();

      addFilesViaInput(container, [
        createFile("a.csv", { size: 10, lastModified: 1 }),
      ]);
      addFilesViaInput(container, [
        createFile("a.csv", { size: 10, lastModified: 1 }),
      ]);

      expect(screen.getByText("1 file")).toBeInTheDocument();
      expect(screen.getAllByText("a.csv")).toHaveLength(1);
    });

    it("keeps files with the same name but different metadata", async () => {
      const { container } = await renderScreen();

      addFilesViaInput(container, [
        createFile("a.csv", { size: 10, lastModified: 1 }),
      ]);
      addFilesViaInput(container, [
        createFile("a.csv", { size: 10, lastModified: 2 }),
      ]);

      expect(screen.getByText("2 files")).toBeInTheDocument();
    });

    it("does nothing when the selection is empty", async () => {
      const { container } = await renderScreen();

      addFilesViaInput(container, []);

      expect(
        screen.queryByRole("button", { name: "Import files" }),
      ).not.toBeInTheDocument();
    });

    it("removes a pending file", async () => {
      const { container } = await renderScreen();

      addFilesViaInput(container, [
        createFile("a.csv", { lastModified: 1 }),
        createFile("b.csv", { lastModified: 2 }),
      ]);

      fireEvent.click(screen.getByRole("button", { name: "Remove a.csv" }));

      expect(screen.queryByText("a.csv")).not.toBeInTheDocument();
      expect(screen.getByText("b.csv")).toBeInTheDocument();
      expect(screen.getByText("1 file")).toBeInTheDocument();
    });

    it("hides the import button after removing every file", async () => {
      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);

      fireEvent.click(screen.getByRole("button", { name: "Remove a.csv" }));

      expect(
        screen.queryByRole("button", { name: "Import files" }),
      ).not.toBeInTheDocument();
    });

    it("opens the file picker when the dropzone is clicked", async () => {
      const { container } = await renderScreen();

      const clickSpy = vi
        .spyOn(getFileInput(container), "click")
        .mockImplementation(() => {});

      fireEvent.click(getDropzone());

      expect(clickSpy).toHaveBeenCalledTimes(1);
    });
  });

  describe("drag and drop", () => {
    it("highlights the dropzone while dragging over it", async () => {
      await renderScreen();

      const dropzone = getDropzone();

      expect(dropzone).toHaveClass("cursor-pointer");

      fireEvent.dragOver(dropzone);

      expect(dropzone).toHaveClass("cursor-copy", "border-primary");

      fireEvent.dragLeave(dropzone);

      expect(dropzone).toHaveClass("cursor-pointer");
      expect(dropzone).not.toHaveClass("cursor-copy");
    });

    it("adds the dropped files and removes the highlight", async () => {
      await renderScreen();

      const dropzone = getDropzone();

      fireEvent.dragOver(dropzone);
      fireEvent.drop(dropzone, {
        dataTransfer: { files: [createFile("dropped.csv")] },
      });

      expect(screen.getByText("dropped.csv")).toBeInTheDocument();
      expect(screen.getByText("1 file")).toBeInTheDocument();
      expect(dropzone).not.toHaveClass("cursor-copy");
    });
  });

  describe("importing", () => {
    it("imports the pending files and shows the result", async () => {
      mockedImportExport.mockResolvedValue(createImportResult());

      const { container } = await renderScreen();

      const files = [
        createFile("a.csv", { lastModified: 1 }),
        createFile("b.csv", { lastModified: 2 }),
      ];

      addFilesViaInput(container, files);

      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(await screen.findByText("Import completed")).toBeInTheDocument();
      expect(
        screen.getByText("Your Letterboxd data has been processed."),
      ).toBeInTheDocument();

      expect(mockedImportExport).toHaveBeenCalledWith(files);

      // pending files are cleared
      expect(screen.queryByText("1 file")).not.toBeInTheDocument();
      expect(screen.queryByText("2 files")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Import files" }),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Missing files:")).not.toBeInTheDocument();
    });

    it("lists the missing files reported by the import", async () => {
      mockedImportExport.mockResolvedValue(
        createImportResult({
          missing: ["missing-1.csv", "missing-2.csv"],
        }),
      );

      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(await screen.findByText("Missing files:")).toBeInTheDocument();
      expect(
        screen.getByText(/missing-1\.csv \| missing-2\.csv/),
      ).toBeInTheDocument();
    });

    it("refreshes the library stats after a successful import", async () => {
      mockedGetLibraryStats
        .mockResolvedValueOnce(createStats({ rated_total: 0 }))
        .mockResolvedValueOnce(
          createStats({ rated_total: 50, rated_with_embedding: 40 }),
        );
      mockedImportExport.mockResolvedValue(createImportResult());

      const { container } = await renderScreen();

      expect(
        screen.getByText("Improve your recommendations"),
      ).toBeInTheDocument();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(
        await screen.findByText("Movies used for your recommendations"),
      ).toBeInTheDocument();
      expect(screen.getByText("40")).toBeInTheDocument();
      expect(screen.getByText("of 50 rated")).toBeInTheDocument();
      expect(mockedGetLibraryStats).toHaveBeenCalledTimes(2);
    });

    it("still completes the import when refreshing the stats fails", async () => {
      mockedGetLibraryStats
        .mockResolvedValueOnce(createStats())
        .mockRejectedValueOnce(new Error("Request failed"));
      mockedImportExport.mockResolvedValue(createImportResult());

      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(await screen.findByText("Import completed")).toBeInTheDocument();
      expect(
        screen.queryByText(/Unable to import/i),
      ).not.toBeInTheDocument();
    });

    it("disables the controls while the import is in progress", async () => {
      let resolveImport!: (value: ImportResult) => void;

      mockedImportExport.mockReturnValue(
        new Promise<ImportResult>((resolve) => {
          resolveImport = resolve;
        }),
      );

      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      // dropzone label + import button label
      expect(await screen.findAllByText("Importing...")).toHaveLength(2);

      expect(getFileInput(container)).toBeDisabled();
      expect(screen.getByRole("button", { name: "Remove a.csv" })).toBeDisabled();
      expect(
        screen.getByRole("button", { name: /Create Swipe Session/i }),
      ).toBeDisabled();

      await act(async () => {
        resolveImport(createImportResult());
      });

      expect(await screen.findByText("Import completed")).toBeInTheDocument();
      expect(screen.queryByText("Importing...")).not.toBeInTheDocument();
    });

    it("ignores files added while importing", async () => {
      mockedImportExport.mockReturnValue(new Promise(() => {}));

      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv", { lastModified: 1 })]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      await screen.findAllByText("Importing...");

      const dropzone = getFileInput(container).closest("button")!;

      fireEvent.drop(dropzone, {
        dataTransfer: { files: [createFile("late.csv", { lastModified: 2 })] },
      });

      expect(screen.queryByText("late.csv")).not.toBeInTheDocument();
      expect(screen.getByText("1 file")).toBeInTheDocument();
    });

    it("renders the backend error message when the import fails", async () => {
      mockedImportExport.mockRejectedValue({
        error: { message: "The ZIP file is corrupted." },
      });

      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(
        await screen.findByText("The ZIP file is corrupted."),
      ).toBeInTheDocument();
      expect(screen.queryByText("Import completed")).not.toBeInTheDocument();
    });

    it("falls back to a default message when the backend error has no message", async () => {
      mockedImportExport.mockRejectedValue({ error: {} });

      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(
        await screen.findByText("Unable to import your Letterboxd data."),
      ).toBeInTheDocument();
    });

    it("falls back to a default message for unexpected errors", async () => {
      mockedImportExport.mockRejectedValue(new Error("boom"));

      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(
        await screen.findByText("Unable to import your Letterboxd data."),
      ).toBeInTheDocument();
    });

    it("keeps the pending files after a failed import so it can be retried", async () => {
      mockedImportExport.mockRejectedValue(new Error("boom"));

      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      await screen.findByText("Unable to import your Letterboxd data.");

      expect(screen.getByText("1 file")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Import files" }),
      ).toBeEnabled();
    });

    it("clears a previous error when new files are added", async () => {
      mockedImportExport.mockRejectedValue(new Error("boom"));

      const { container } = await renderScreen();

      addFilesViaInput(container, [createFile("a.csv", { lastModified: 1 })]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      await screen.findByText("Unable to import your Letterboxd data.");

      addFilesViaInput(container, [createFile("b.csv", { lastModified: 2 })]);

      expect(
        screen.queryByText("Unable to import your Letterboxd data."),
      ).not.toBeInTheDocument();
    });
  });
});