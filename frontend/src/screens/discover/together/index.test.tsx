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

import TogetherScreen from "./index";
import { importExport, type ImportResult } from "../../../services/imports";
import { createPairedSwipeSession } from "../../../services/swipeSessions";
import { getErrorMessage } from "../../../utils/errors";

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

vi.mock("../../../services/swipeSessions", () => ({
  createPairedSwipeSession: vi.fn(),
}));

vi.mock("../../../utils/errors", () => ({
  getErrorMessage: vi.fn(),
}));

const mockedImportExport = vi.mocked(importExport);
const mockedCreatePairedSession = vi.mocked(createPairedSwipeSession);
const mockedGetErrorMessage = vi.mocked(getErrorMessage);

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

const renderScreen = () =>
  render(
    <MemoryRouter>
      <TogetherScreen />
    </MemoryRouter>,
  );

const getFileInput = (container: HTMLElement) =>
  container.querySelector('input[type="file"]') as HTMLInputElement;

const getDropzone = () =>
  screen.getByRole("button", { name: /Drop files or browse/i });

const getCodeInput = () => screen.getByLabelText("Invite code or link");

const getJoinButton = () => screen.getByRole("button", { name: "Join" });

const getCreateButton = () =>
  screen.getByRole("button", { name: /Create Paired Session/i });

const typeCode = (value: string) => {
  fireEvent.change(getCodeInput(), { target: { value } });
};

const addFilesViaInput = (container: HTMLElement, files: File[]) => {
  fireEvent.change(getFileInput(container), { target: { files } });
};

describe("TogetherScreen", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();

    mockedGetErrorMessage.mockReturnValue("Something went wrong.");
  });

  describe("layout", () => {
    it("renders the header, the invite section and the main cards", () => {
      renderScreen();

      expect(
        screen.getByRole("heading", { name: "Discover together" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "Got an invite?" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "Create Paired Session" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "Import Letterboxd" }),
      ).toBeInTheDocument();
      expect(getCodeInput()).toHaveAttribute(
        "placeholder",
        "Invite code or link",
      );
      expect(screen.getByText("What can you import?")).toBeInTheDocument();
      expect(screen.getByText("Supported files")).toBeInTheDocument();
    });

    it("renders a link back to home", () => {
      renderScreen();

      expect(
        screen.getByRole("link", { name: /Back to home/i }),
      ).toHaveAttribute("href", "/");
    });

    it("does not render the import button, result or error initially", () => {
      renderScreen();

      expect(
        screen.queryByRole("button", { name: "Import files" }),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Import completed")).not.toBeInTheDocument();
      expect(
        screen.queryByText("Something went wrong."),
      ).not.toBeInTheDocument();
    });
  });

  describe("joining with an invite", () => {
    it("disables the join button when the input is empty", () => {
      renderScreen();

      expect(getJoinButton()).toBeDisabled();
    });

    it("disables the join button when the input only has whitespace", () => {
      renderScreen();

      typeCode("   ");

      expect(getJoinButton()).toBeDisabled();
    });

    it("enables the join button once a code is typed", () => {
      renderScreen();

      typeCode("ABC123");

      expect(getJoinButton()).toBeEnabled();
    });

    it("navigates to the join page with the typed code", () => {
      renderScreen();

      typeCode("ABC123");
      fireEvent.click(getJoinButton());

      expect(mockNavigate).toHaveBeenCalledTimes(1);
      expect(mockNavigate).toHaveBeenCalledWith("/join/ABC123");
    });

    it("trims whitespace around the code", () => {
      renderScreen();

      typeCode("   ABC123  ");
      fireEvent.click(getJoinButton());

      expect(mockNavigate).toHaveBeenCalledWith("/join/ABC123");
    });

    it("extracts the code from a full invite link", () => {
      renderScreen();

      typeCode("https://example.com/join/XYZ789");
      fireEvent.click(getJoinButton());

      expect(mockNavigate).toHaveBeenCalledWith("/join/XYZ789");
    });

    it("ignores trailing slashes in the link", () => {
      renderScreen();

      typeCode("https://example.com/join/XYZ789///");
      fireEvent.click(getJoinButton());

      expect(mockNavigate).toHaveBeenCalledWith("/join/XYZ789");
    });

    it("ignores query strings and hashes in the link", () => {
      renderScreen();

      typeCode("https://example.com/join/XYZ789?utm=1");
      fireEvent.click(getJoinButton());

      expect(mockNavigate).toHaveBeenLastCalledWith("/join/XYZ789");

      typeCode("https://example.com/join/QWE456#section");
      fireEvent.click(getJoinButton());

      expect(mockNavigate).toHaveBeenLastCalledWith("/join/QWE456");
    });

    it("joins when pressing Enter in the input", () => {
      renderScreen();

      typeCode("ABC123");
      fireEvent.keyDown(getCodeInput(), { key: "Enter" });

      expect(mockNavigate).toHaveBeenCalledWith("/join/ABC123");
    });

    it("does not navigate when pressing Enter with an empty input", () => {
      renderScreen();

      fireEvent.keyDown(getCodeInput(), { key: "Enter" });

      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it("does not navigate when pressing other keys", () => {
      renderScreen();

      typeCode("ABC123");
      fireEvent.keyDown(getCodeInput(), { key: "a" });

      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it("disables the join button while a session is being created", () => {
      mockedCreatePairedSession.mockReturnValue(new Promise(() => {}));

      renderScreen();

      typeCode("ABC123");
      fireEvent.click(getCreateButton());

      expect(getJoinButton()).toBeDisabled();
    });
  });

  describe("creating a session", () => {
    it("creates the session and navigates to it with the invite", async () => {
      const invite = { code: "ABC123", url: "https://example.com/join/ABC123" };

      mockedCreatePairedSession.mockResolvedValue({
        session: { id: "paired-1" },
        invite,
      } as never);

      renderScreen();

      fireEvent.click(getCreateButton());

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith(
          "/discover/together/paired-1",
          { state: { invite } },
        );
      });

      expect(mockedCreatePairedSession).toHaveBeenCalledTimes(1);
    });

    it("shows a loading label and disables the button while creating", async () => {
      mockedCreatePairedSession.mockReturnValue(new Promise(() => {}));

      renderScreen();

      fireEvent.click(getCreateButton());

      expect(await screen.findByText("Creating session...")).toBeInTheDocument();
      expect(getCreateButton()).toBeDisabled();
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it("renders the error message when creating the session fails", async () => {
      const failure = new Error("Request failed");

      mockedCreatePairedSession.mockRejectedValue(failure);
      mockedGetErrorMessage.mockReturnValue("Could not create the session.");

      renderScreen();

      fireEvent.click(getCreateButton());

      expect(
        await screen.findByText("Could not create the session."),
      ).toBeInTheDocument();
      expect(mockedGetErrorMessage).toHaveBeenCalledWith(failure);
      expect(mockNavigate).not.toHaveBeenCalled();
      expect(screen.getByText("Create session")).toBeInTheDocument();
      expect(getCreateButton()).toBeEnabled();
    });

    it("clears the error when trying again", async () => {
      mockedCreatePairedSession
        .mockRejectedValueOnce(new Error("Request failed"))
        .mockReturnValueOnce(new Promise(() => {}));
      mockedGetErrorMessage.mockReturnValue("Could not create the session.");

      renderScreen();

      fireEvent.click(getCreateButton());

      expect(
        await screen.findByText("Could not create the session."),
      ).toBeInTheDocument();

      fireEvent.click(getCreateButton());

      await waitFor(() => {
        expect(
          screen.queryByText("Could not create the session."),
        ).not.toBeInTheDocument();
      });
    });
  });

  describe("selecting files", () => {
    it("lists a selected file with its name and size", () => {
      const { container } = renderScreen();

      addFilesViaInput(container, [createFile("diary.csv", { size: 2048 })]);

      expect(screen.getAllByText("diary.csv")).toHaveLength(2); // pending + supported list
      expect(screen.getByText("2.0 KB")).toBeInTheDocument();
      expect(screen.getByText("1 file")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Import files" }),
      ).toBeInTheDocument();
    });

    it("uses the plural label with several files", () => {
      const { container } = renderScreen();

      addFilesViaInput(container, [
        createFile("a.csv", { lastModified: 1 }),
        createFile("b.csv", { lastModified: 2 }),
      ]);

      expect(screen.getByText("2 files")).toBeInTheDocument();
    });

    it("formats sizes in B, KB and MB", () => {
      const { container } = renderScreen();

      addFilesViaInput(container, [
        createFile("small.csv", { size: 100, lastModified: 1 }),
        createFile("medium.csv", { size: 1536, lastModified: 2 }),
        createFile("large.csv", { size: 5 * 1024 * 1024, lastModified: 3 }),
      ]);

      expect(screen.getByText("100 B")).toBeInTheDocument();
      expect(screen.getByText("1.5 KB")).toBeInTheDocument();
      expect(screen.getByText("5.0 MB")).toBeInTheDocument();
    });

    it("ignores duplicated files", () => {
      const { container } = renderScreen();

      addFilesViaInput(container, [
        createFile("a.csv", { size: 10, lastModified: 1 }),
      ]);
      addFilesViaInput(container, [
        createFile("a.csv", { size: 10, lastModified: 1 }),
      ]);

      expect(screen.getByText("1 file")).toBeInTheDocument();
    });

    it("removes a pending file", () => {
      const { container } = renderScreen();

      addFilesViaInput(container, [
        createFile("a.csv", { lastModified: 1 }),
        createFile("b.csv", { lastModified: 2 }),
      ]);

      fireEvent.click(screen.getByRole("button", { name: "Remove a.csv" }));

      expect(screen.queryByText("a.csv")).not.toBeInTheDocument();
      expect(screen.getByText("b.csv")).toBeInTheDocument();
      expect(screen.getByText("1 file")).toBeInTheDocument();
    });

    it("opens the file picker when the dropzone is clicked", () => {
      const { container } = renderScreen();

      const clickSpy = vi
        .spyOn(getFileInput(container), "click")
        .mockImplementation(() => {});

      fireEvent.click(getDropzone());

      expect(clickSpy).toHaveBeenCalledTimes(1);
    });

    it("highlights the dropzone while dragging and adds dropped files", () => {
      renderScreen();

      const dropzone = getDropzone();

      fireEvent.dragOver(dropzone);

      expect(dropzone).toHaveClass("cursor-copy");

      fireEvent.dragLeave(dropzone);

      expect(dropzone).not.toHaveClass("cursor-copy");

      fireEvent.dragOver(dropzone);
      fireEvent.drop(dropzone, {
        dataTransfer: { files: [createFile("dropped.csv")] },
      });

      expect(screen.getByText("dropped.csv")).toBeInTheDocument();
      expect(dropzone).not.toHaveClass("cursor-copy");
    });
  });

  describe("importing", () => {
    it("imports the pending files and shows the result", async () => {
      mockedImportExport.mockResolvedValue(createImportResult());

      const { container } = renderScreen();

      const files = [
        createFile("a.csv", { lastModified: 1 }),
        createFile("b.csv", { lastModified: 2 }),
      ];

      addFilesViaInput(container, files);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(await screen.findByText("Import completed")).toBeInTheDocument();
      expect(mockedImportExport).toHaveBeenCalledWith(files);

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

      const { container } = renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(await screen.findByText("Missing files:")).toBeInTheDocument();
      expect(
        screen.getByText(/missing-1\.csv \| missing-2\.csv/),
      ).toBeInTheDocument();
    });

    it("disables the controls while the import is in progress", async () => {
      let resolveImport!: (value: ImportResult) => void;

      mockedImportExport.mockReturnValue(
        new Promise<ImportResult>((resolve) => {
          resolveImport = resolve;
        }),
      );

      const { container } = renderScreen();

      typeCode("ABC123");
      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(await screen.findAllByText("Importing...")).toHaveLength(2);

      expect(getFileInput(container)).toBeDisabled();
      expect(screen.getByRole("button", { name: "Remove a.csv" })).toBeDisabled();
      expect(getCreateButton()).toBeDisabled();
      expect(getJoinButton()).toBeDisabled();

      await act(async () => {
        resolveImport(createImportResult());
      });

      expect(await screen.findByText("Import completed")).toBeInTheDocument();
      expect(getJoinButton()).toBeEnabled();
    });

    it("renders the backend error message when the import fails", async () => {
      mockedImportExport.mockRejectedValue({
        error: { message: "The ZIP file is corrupted." },
      });

      const { container } = renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(
        await screen.findByText("The ZIP file is corrupted."),
      ).toBeInTheDocument();
      expect(screen.queryByText("Import completed")).not.toBeInTheDocument();
    });

    it("falls back to a default message when the backend error has no message", async () => {
      mockedImportExport.mockRejectedValue({ error: {} });

      const { container } = renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(
        await screen.findByText("Unable to import your Letterboxd data."),
      ).toBeInTheDocument();
    });

    it("falls back to a default message for unexpected errors", async () => {
      mockedImportExport.mockRejectedValue(new Error("boom"));

      const { container } = renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      expect(
        await screen.findByText("Unable to import your Letterboxd data."),
      ).toBeInTheDocument();
    });

    it("keeps the pending files after a failed import so it can be retried", async () => {
      mockedImportExport.mockRejectedValue(new Error("boom"));

      const { container } = renderScreen();

      addFilesViaInput(container, [createFile("a.csv")]);
      fireEvent.click(screen.getByRole("button", { name: "Import files" }));

      await screen.findByText("Unable to import your Letterboxd data.");

      expect(screen.getByText("1 file")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Import files" }),
      ).toBeEnabled();
    });
  });
});