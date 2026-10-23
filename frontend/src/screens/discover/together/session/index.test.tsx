import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import type { ReactNode } from "react";
import "@testing-library/jest-dom/vitest";

import PairedSessionScreen from "./index";
import { useLeaveSession } from "../../../../hooks/useLeaveSession";
import { usePairedSession } from "../../../../hooks/usePairedSession";
import {
  endSwipeSession,
  regeneratePairedInvite,
} from "../../../../services/swipeSessions";

const { router } = vi.hoisted(() => ({
  router: {
    params: { id: "session-1" as string | undefined },
    location: { state: null as unknown },
  },
}));

vi.mock("react-router-dom", () => ({
  useParams: () => router.params,
  useLocation: () => router.location,
}));

vi.mock("../../../../components/ErrorScreen", () => ({
  default: ({
    message,
    buttonText,
  }: {
    message: string;
    buttonText?: string;
  }) => (
    <div data-testid="error-screen">
      <p>{message}</p>
      {buttonText && <span>{buttonText}</span>}
    </div>
  ),
}));

vi.mock("../../../../components/FailurePanel", () => ({
  default: ({
    title,
    text,
    onRetry,
  }: {
    title: string;
    text: string;
    onRetry: () => void;
  }) => (
    <div data-testid="failure-panel">
      <h3>{title}</h3>
      <p>{text}</p>
      <button type="button" onClick={onRetry}>
        Retry start
      </button>
    </div>
  ),
}));

vi.mock("../../../../components/Waiting", () => ({
  default: ({ title, text }: { title: string; text: string }) => (
    <div data-testid="waiting">
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  ),
}));

vi.mock("../../../../components/SessionLobby", () => ({
  default: ({
    kind,
    phase,
    initialInvite,
    onRegenerate,
    onImported,
    leave,
    children,
  }: {
    kind: string;
    phase: string;
    initialInvite: unknown;
    onRegenerate: () => void;
    onImported: () => void;
    leave: unknown;
    children?: ReactNode;
  }) => (
    <div
      data-testid="session-lobby"
      data-kind={kind}
      data-phase={phase}
      data-invite={JSON.stringify(initialInvite)}
      data-leave={JSON.stringify(leave)}
    >
      <button type="button" onClick={onRegenerate}>
        Regenerate invite
      </button>
      <button type="button" onClick={onImported}>
        Imported
      </button>
      {children}
    </div>
  ),
}));

vi.mock("../../individual/session", () => ({
  default: ({ paired }: { paired: { marker?: string } }) => (
    <div data-testid="discover-session" data-marker={paired?.marker} />
  ),
}));

vi.mock("../../../../hooks/useLeaveSession", () => ({
  useLeaveSession: vi.fn(),
}));

vi.mock("../../../../hooks/usePairedSession", () => ({
  usePairedSession: vi.fn(),
}));

vi.mock("../../../../services/swipeSessions", () => ({
  endSwipeSession: vi.fn(),
  regeneratePairedInvite: vi.fn(),
}));

const mockedUsePairedSession = vi.mocked(usePairedSession);
const mockedUseLeaveSession = vi.mocked(useLeaveSession);
const mockedRegenerateInvite = vi.mocked(regeneratePairedInvite);

type Paired = ReturnType<typeof usePairedSession>;

const createPaired = (overrides: Record<string, unknown> = {}) =>
  ({
    marker: "paired-controller",
    fatal: null,
    phase: "waiting",
    hasBeenActive: false,
    state: { members: [] },
    error: null,
    startError: null,
    refresh: vi.fn(),
    retryStart: vi.fn(),
    ...overrides,
  }) as unknown as Paired & {
    refresh: ReturnType<typeof vi.fn>;
    retryStart: ReturnType<typeof vi.fn>;
  };

const setup = (overrides: Record<string, unknown> = {}) => {
  const paired = createPaired(overrides);

  mockedUsePairedSession.mockReturnValue(paired);

  return { paired, ...render(<PairedSessionScreen />) };
};

describe("PairedSessionScreen", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();

    router.params.id = "session-1";
    router.location.state = null;

    mockedUseLeaveSession.mockReturnValue({
      leaving: false,
    } as unknown as ReturnType<typeof useLeaveSession>);
  });

  describe("hooks", () => {
    it("loads the paired session for the current id", () => {
      setup();

      expect(mockedUsePairedSession).toHaveBeenCalledWith("session-1");
    });

    it("configures leaving the session with the swipe session service", () => {
      setup();

      expect(mockedUseLeaveSession).toHaveBeenCalledWith(
        "session-1",
        endSwipeSession,
        "session",
      );
    });
  });

  describe("fatal errors", () => {
    it("renders a not found screen", () => {
      setup({ fatal: "not_found" });

      expect(
        screen.getByText(
          "This swipe session does not exist or is no longer available.",
        ),
      ).toBeInTheDocument();
      expect(screen.getByText("Back to home")).toBeInTheDocument();
      expect(screen.queryByTestId("session-lobby")).not.toBeInTheDocument();
    });

    it("renders a forbidden screen", () => {
      setup({ fatal: "forbidden" });

      expect(
        screen.getByText("You are not a member of this session."),
      ).toBeInTheDocument();
      expect(screen.getByText("Back to home")).toBeInTheDocument();
    });

    it("renders a closed screen", () => {
      setup({ fatal: "closed" });

      expect(
        screen.getByText("This session is no longer available."),
      ).toBeInTheDocument();
      expect(screen.getByText("Back to home")).toBeInTheDocument();
    });

    it("gives fatal errors priority over an active session", () => {
      setup({ fatal: "forbidden", phase: "active", hasBeenActive: true });

      expect(
        screen.getByText("You are not a member of this session."),
      ).toBeInTheDocument();
      expect(screen.queryByTestId("discover-session")).not.toBeInTheDocument();
    });
  });

  describe("active session", () => {
    it("renders the discover screen when the session is active", () => {
      setup({ phase: "active" });

      expect(screen.getByTestId("discover-session")).toBeInTheDocument();
      expect(screen.queryByTestId("session-lobby")).not.toBeInTheDocument();
    });

    it("passes the paired controller to the discover screen", () => {
      setup({ phase: "active" });

      expect(screen.getByTestId("discover-session")).toHaveAttribute(
        "data-marker",
        "paired-controller",
      );
    });

    it("keeps rendering the discover screen once the session has been active", () => {
      setup({ phase: "closed", hasBeenActive: true });

      expect(screen.getByTestId("discover-session")).toBeInTheDocument();
      expect(
        screen.queryByText("This session was closed before it started."),
      ).not.toBeInTheDocument();
    });
  });

  describe("closed before starting", () => {
    it("renders a closed before it started screen", () => {
      setup({ phase: "closed", hasBeenActive: false });

      expect(
        screen.getByText("This session was closed before it started."),
      ).toBeInTheDocument();
      expect(screen.getByText("Back to home")).toBeInTheDocument();
      expect(screen.queryByTestId("session-lobby")).not.toBeInTheDocument();
    });
  });

  describe("lobby", () => {
    it("renders the lobby for the current phase", () => {
      setup({ phase: "waiting" });

      const lobby = screen.getByTestId("session-lobby");

      expect(lobby).toHaveAttribute("data-kind", "swipe");
      expect(lobby).toHaveAttribute("data-phase", "waiting");
    });

    it("passes the leave controller to the lobby", () => {
      mockedUseLeaveSession.mockReturnValue({
        leaving: true,
      } as unknown as ReturnType<typeof useLeaveSession>);

      setup();

      expect(screen.getByTestId("session-lobby")).toHaveAttribute(
        "data-leave",
        JSON.stringify({ leaving: true }),
      );
    });

    it("uses the invite received through the router state", () => {
      const invite = { code: "ABC123", url: "https://example.com/join/ABC123" };

      router.location.state = { invite };

      setup();

      expect(screen.getByTestId("session-lobby")).toHaveAttribute(
        "data-invite",
        JSON.stringify(invite),
      );
    });

    it("falls back to a null invite when there is no router state", () => {
      router.location.state = null;

      setup();

      expect(screen.getByTestId("session-lobby")).toHaveAttribute(
        "data-invite",
        "null",
      );
    });

    it("falls back to a null invite when the router state has no invite", () => {
      router.location.state = { somethingElse: true };

      setup();

      expect(screen.getByTestId("session-lobby")).toHaveAttribute(
        "data-invite",
        "null",
      );
    });

    it("regenerates the invite for the current session", () => {
      setup();

      fireEvent.click(screen.getByRole("button", { name: "Regenerate invite" }));

      expect(mockedRegenerateInvite).toHaveBeenCalledTimes(1);
      expect(mockedRegenerateInvite).toHaveBeenCalledWith("session-1");
    });

    it("refreshes the session after an import", () => {
      const { paired } = setup();

      fireEvent.click(screen.getByRole("button", { name: "Imported" }));

      expect(paired.refresh).toHaveBeenCalledTimes(1);
    });
  });

  describe("starting phase", () => {
    it("renders the waiting indicator while the session starts", () => {
      setup({ phase: "starting" });

      expect(screen.getByTestId("waiting")).toBeInTheDocument();
      expect(
        screen.getByText("Picking movies for both of you…"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("This usually takes a few seconds."),
      ).toBeInTheDocument();
    });

    it("does not render the waiting indicator in other phases", () => {
      setup({ phase: "waiting" });

      expect(screen.queryByTestId("waiting")).not.toBeInTheDocument();
    });
  });

  describe("failed phase", () => {
    it("renders the failure panel with the start error", () => {
      setup({ phase: "failed", startError: "Not enough common movies." });

      expect(screen.getByTestId("failure-panel")).toBeInTheDocument();
      expect(
        screen.getByText("Something went wrong starting the session"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Not enough common movies."),
      ).toBeInTheDocument();
    });

    it("falls back to a default message when there is no start error", () => {
      setup({ phase: "failed", startError: null });

      expect(
        screen.getByText("Your data is safe. Try again in a moment."),
      ).toBeInTheDocument();
    });

    it("retries starting the session", () => {
      const { paired } = setup({ phase: "failed" });

      fireEvent.click(screen.getByRole("button", { name: "Retry start" }));

      expect(paired.retryStart).toHaveBeenCalledTimes(1);
    });

    it("does not render the failure panel in other phases", () => {
      setup({ phase: "starting" });

      expect(screen.queryByTestId("failure-panel")).not.toBeInTheDocument();
    });
  });

  describe("lobby error", () => {
    it("renders the paired session error inside the lobby", () => {
      setup({ error: "Could not refresh the session." });

      expect(
        screen.getByText("Could not refresh the session."),
      ).toBeInTheDocument();
    });

    it("does not render an error box when there is no error", () => {
      const { container } = setup({ error: null });

      expect(container.querySelector(".text-red-400")).not.toBeInTheDocument();
    });

    it("renders the error alongside the failure panel", () => {
      setup({
        phase: "failed",
        startError: "Start failed.",
        error: "Could not refresh the session.",
      });

      expect(screen.getByText("Start failed.")).toBeInTheDocument();
      expect(
        screen.getByText("Could not refresh the session."),
      ).toBeInTheDocument();
    });
  });
});