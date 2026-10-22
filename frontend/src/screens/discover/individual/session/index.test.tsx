import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import DiscoverSessionScreen from "./index";
import { getStreamingCountries } from "../../../../components/StreamingProviders";
import { useEndSwipeSession } from "../../../../hooks/useEndSwipeSession";
import { useHeartbeat } from "../../../../hooks/useHeartbeat";
import type { PairedSessionController } from "../../../../hooks/usePairedSession";
import { useSwipeDeck } from "../../../../hooks/useSwipeDeck";

const { mockParams } = vi.hoisted(() => ({
  mockParams: { id: "session-1" as string | undefined },
}));

vi.mock("react-router-dom", () => ({
  useParams: () => mockParams,
}));

vi.mock("lucide-react", () => ({
  LogOut: () => <svg data-testid="logout-icon" />,
}));

vi.mock("../../../../components/AppLogo", () => ({
  default: () => <div data-testid="app-logo" />,
}));

vi.mock("../../../../components/ErrorScreen", () => ({
  default: ({
    message,
    buttonText,
    onRetry,
  }: {
    message: string;
    buttonText?: string;
    onRetry?: () => void;
  }) => (
    <div data-testid="error-screen">
      <p>{message}</p>
      {buttonText && <span>{buttonText}</span>}
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  ),
}));

vi.mock("../../../../components/MovieInformation", () => ({
  default: ({
    movie,
    streamingCountries,
  }: {
    movie?: { title: string } | null;
    streamingCountries: string[];
  }) => (
    <div data-testid="movie-information">
      {movie?.title}|{streamingCountries.join(",")}
    </div>
  ),
}));

vi.mock("../../../../components/PairedSessionOverlay", () => ({
  default: ({ sessionId }: { sessionId: string }) => (
    <div data-testid="paired-overlay">{sessionId}</div>
  ),
}));

vi.mock("../../../../components/StreamingProviders", () => ({
  getStreamingCountries: vi.fn(),
}));

vi.mock("../../../../components/SwipeActionBar", () => ({
  default: ({
    disabled,
    onSkip,
    onWatched,
    onWatchlist,
  }: {
    disabled: boolean;
    onSkip: () => void;
    onWatched: () => void;
    onWatchlist: () => void;
  }) => (
    <div data-testid="swipe-action-bar" data-disabled={String(disabled)}>
      <button type="button" onClick={onSkip}>
        Skip
      </button>
      <button type="button" onClick={onWatched}>
        Watched
      </button>
      <button type="button" onClick={onWatchlist}>
        Watchlist
      </button>
    </div>
  ),
}));

vi.mock("../../../../components/SwipeInstructions", () => ({
  default: () => <div data-testid="swipe-instructions" />,
}));

vi.mock("../../../../components/SwipeMovieCard", () => ({
  default: ({
    movie,
    candidateId,
    sessionId,
    onSwipe,
    onShowInfo,
  }: {
    movie: { title: string };
    candidateId: string;
    sessionId: string;
    onSwipe: (direction: "left" | "right") => void;
    onShowInfo: () => void;
  }) => (
    <div data-testid="swipe-movie-card">
      <span>{movie.title}</span>
      <span data-testid="card-candidate">{candidateId}</span>
      <span data-testid="card-session">{sessionId}</span>
      <button type="button" onClick={() => onSwipe("right")}>
        Card swipe right
      </button>
      <button type="button" onClick={onShowInfo}>
        Show info
      </button>
    </div>
  ),
}));

vi.mock("../../../../hooks/useEndSwipeSession", () => ({
  useEndSwipeSession: vi.fn(),
}));

vi.mock("../../../../hooks/useHeartbeat", () => ({
  useHeartbeat: vi.fn(),
}));

vi.mock("../../../../hooks/useSwipeDeck", () => ({
  useSwipeDeck: vi.fn(),
}));

vi.mock("../../../../components/modal/EndSessionModal", () => ({
  default: ({
    isEndingSession,
    error,
    onClose,
    onGoHome,
    onDownloadCsv,
  }: {
    isEndingSession: boolean;
    error: string | null;
    onClose: () => void;
    onGoHome: () => void;
    onDownloadCsv: () => void;
  }) => (
    <div role="dialog" aria-label="End session modal">
      <span data-testid="ending-state">{String(isEndingSession)}</span>
      {error && <p>{error}</p>}
      <button type="button" onClick={onClose}>
        Close end modal
      </button>
      <button type="button" onClick={onGoHome}>
        Go home
      </button>
      <button type="button" onClick={onDownloadCsv}>
        Download CSV
      </button>
    </div>
  ),
}));

vi.mock("../../../../components/modal/MovieInfoModal", () => ({
  default: ({
    movie,
    streamingCountries,
    onClose,
  }: {
    movie: { title: string };
    streamingCountries: string[];
    onClose: () => void;
  }) => (
    <div role="dialog" aria-label="Movie info modal">
      <span>
        {movie.title}|{streamingCountries.join(",")}
      </span>
      <button type="button" onClick={onClose}>
        Close info modal
      </button>
    </div>
  ),
}));

vi.mock("../../../../components/modal/RateMovieModal", () => ({
  default: ({
    movieId,
    movieTitle,
    onClose,
    onSaved,
  }: {
    movieId: number;
    movieTitle: string;
    onClose: () => void;
    onSaved: () => void;
  }) => (
    <div role="dialog" aria-label="Rate movie modal">
      <span>
        Rate {movieTitle} ({movieId})
      </span>
      <button type="button" onClick={onClose}>
        Close rate modal
      </button>
      <button type="button" onClick={onSaved}>
        Save rating
      </button>
    </div>
  ),
}));

const mockedUseSwipeDeck = vi.mocked(useSwipeDeck);
const mockedUseHeartbeat = vi.mocked(useHeartbeat);
const mockedUseEndSwipeSession = vi.mocked(useEndSwipeSession);
const mockedGetStreamingCountries = vi.mocked(getStreamingCountries);

type Deck = ReturnType<typeof useSwipeDeck>;

const createDeck = (overrides: Record<string, unknown> = {}) =>
  ({
    movie: { tmdb_id: 550, title: "Fight Club" },
    candidateId: "candidate-1",
    finished: false,
    error: null,
    isLoading: false,
    locked: false,
    sessionNotFound: false,
    sessionFinished: false,
    isPromotingBackCard: false,
    swipeDirection: null,
    dragX: 0,
    dragRotate: 0,
    cardOpacity: 1,
    backCardY: 0,
    swipe: vi.fn(),
    retry: vi.fn(),
    completePromotion: vi.fn(),
    ...overrides,
  }) as unknown as Deck;

const createEndSession = (overrides: Record<string, unknown> = {}) => ({
  isEndingSession: false,
  endSessionError: null as string | null,
  clearEndSessionError: vi.fn(),
  handleGoHome: vi.fn(),
  handleDownloadCsv: vi.fn(),
  ...overrides,
});

const createPaired = (overrides: Record<string, unknown> = {}) =>
  ({
    ended: false,
    ...overrides,
  }) as unknown as PairedSessionController;

let endSession: ReturnType<typeof createEndSession>;

const setup = (
  deckOverrides: Record<string, unknown> = {},
  paired?: PairedSessionController,
) => {
  const deck = createDeck(deckOverrides);

  mockedUseSwipeDeck.mockReturnValue(deck);

  const utils = render(<DiscoverSessionScreen paired={paired} />);

  return { deck, ...utils };
};

describe("DiscoverSessionScreen", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();

    mockParams.id = "session-1";
    endSession = createEndSession();

    mockedUseEndSwipeSession.mockReturnValue(
      endSession as unknown as ReturnType<typeof useEndSwipeSession>,
    );
    mockedGetStreamingCountries.mockReturnValue(["ES", "US"] as never);
  });

  describe("hooks", () => {
    it("loads the deck and the end-session logic for the current session", () => {
      setup();

      expect(mockedUseSwipeDeck).toHaveBeenCalledWith("session-1");
      expect(mockedUseEndSwipeSession).toHaveBeenCalledWith({
        id: "session-1",
      });
    });

    it("keeps the heartbeat active while the deck is running", () => {
      setup();

      expect(mockedUseHeartbeat).toHaveBeenCalledWith("session-1", true);
    });

    it("stops the heartbeat when the deck is finished", () => {
      setup({ finished: true });

      expect(mockedUseHeartbeat).toHaveBeenCalledWith("session-1", false);
    });

    it("stops the heartbeat when the deck has an error", () => {
      setup({ error: "Something failed" });

      expect(mockedUseHeartbeat).toHaveBeenCalledWith("session-1", false);
    });
  });

  describe("swipe view", () => {
    it("renders the card, the action bar and the movie information", () => {
      setup();

      expect(screen.getByTestId("swipe-movie-card")).toBeInTheDocument();
      expect(screen.getByText("Fight Club")).toBeInTheDocument();
      expect(screen.getByTestId("card-candidate")).toHaveTextContent(
        "candidate-1",
      );
      expect(screen.getByTestId("card-session")).toHaveTextContent(
        "session-1",
      );
      expect(screen.getByTestId("swipe-action-bar")).toBeInTheDocument();
      expect(screen.getByTestId("movie-information")).toHaveTextContent(
        "Fight Club|ES,US",
      );
      expect(screen.getAllByTestId("swipe-instructions").length).toBeGreaterThan(
        0,
      );
      expect(screen.getAllByTestId("app-logo").length).toBeGreaterThan(0);
    });

    it("computes the streaming countries from the current movie", () => {
      const { deck } = setup();

      expect(mockedGetStreamingCountries).toHaveBeenCalledWith(deck.movie);
    });

    it("renders a placeholder while the deck is loading without a movie", () => {
      setup({ movie: null, candidateId: null, isLoading: true });

      expect(screen.getByText("?")).toBeInTheDocument();
      expect(screen.queryByTestId("swipe-movie-card")).not.toBeInTheDocument();
    });

    it("renders neither the card nor the placeholder when there is no movie and it is not loading", () => {
      setup({ movie: null, candidateId: null, isLoading: false });

      expect(screen.queryByText("?")).not.toBeInTheDocument();
      expect(screen.queryByTestId("swipe-movie-card")).not.toBeInTheDocument();
    });

    it("disables the action bar while the deck is locked", () => {
      setup({ locked: true });

      expect(screen.getByTestId("swipe-action-bar")).toHaveAttribute(
        "data-disabled",
        "true",
      );
    });

    it("enables the action bar when the deck is not locked", () => {
      setup({ locked: false });

      expect(screen.getByTestId("swipe-action-bar")).toHaveAttribute(
        "data-disabled",
        "false",
      );
    });

    it("forwards swipes from the card to the deck", () => {
      const { deck } = setup();

      fireEvent.click(screen.getByRole("button", { name: "Card swipe right" }));

      expect(deck.swipe).toHaveBeenCalledWith("right");
    });

    it("swipes left when skipping", () => {
      const { deck } = setup();

      fireEvent.click(screen.getByRole("button", { name: "Skip" }));

      expect(deck.swipe).toHaveBeenCalledTimes(1);
      expect(deck.swipe).toHaveBeenCalledWith("left");
    });

    it("swipes right when adding to the watchlist", () => {
      const { deck } = setup();

      fireEvent.click(screen.getByRole("button", { name: "Watchlist" }));

      expect(deck.swipe).toHaveBeenCalledTimes(1);
      expect(deck.swipe).toHaveBeenCalledWith("right");
    });
  });

  describe("paired overlay", () => {
    it("does not render the overlay for individual sessions", () => {
      setup();

      expect(screen.queryByTestId("paired-overlay")).not.toBeInTheDocument();
    });

    it("renders the overlay for paired sessions", () => {
      setup({}, createPaired());

      expect(screen.getByTestId("paired-overlay")).toHaveTextContent(
        "session-1",
      );
    });

    it("does not render the overlay when there is no session id", () => {
      mockParams.id = undefined;

      setup({}, createPaired());

      expect(screen.queryByTestId("paired-overlay")).not.toBeInTheDocument();
    });
  });

  describe("rating a movie", () => {
    it("opens the rate modal for the current movie when marking it as watched", () => {
      setup();

      expect(
        screen.queryByRole("dialog", { name: "Rate movie modal" }),
      ).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Watched" }));

      expect(
        screen.getByRole("dialog", { name: "Rate movie modal" }),
      ).toBeInTheDocument();
      expect(screen.getByText("Rate Fight Club (550)")).toBeInTheDocument();
    });

    it("closes the modal and swipes left once the rating is saved", () => {
      const { deck } = setup();

      fireEvent.click(screen.getByRole("button", { name: "Watched" }));
      fireEvent.click(screen.getByRole("button", { name: "Save rating" }));

      expect(
        screen.queryByRole("dialog", { name: "Rate movie modal" }),
      ).not.toBeInTheDocument();
      expect(deck.swipe).toHaveBeenCalledTimes(1);
      expect(deck.swipe).toHaveBeenCalledWith("left");
    });

    it("closes the modal without swiping when it is dismissed", () => {
      const { deck } = setup();

      fireEvent.click(screen.getByRole("button", { name: "Watched" }));
      fireEvent.click(screen.getByRole("button", { name: "Close rate modal" }));

      expect(
        screen.queryByRole("dialog", { name: "Rate movie modal" }),
      ).not.toBeInTheDocument();
      expect(deck.swipe).not.toHaveBeenCalled();
    });
  });

  describe("movie info modal", () => {
    it("opens the info modal from the card", () => {
      setup();

      expect(
        screen.queryByRole("dialog", { name: "Movie info modal" }),
      ).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Show info" }));

      expect(
        screen.getByRole("dialog", { name: "Movie info modal" }),
      ).toBeInTheDocument();
      expect(screen.getByText("Fight Club|ES,US", { selector: "span" }))
        .toBeInTheDocument();
    });

    it("closes the info modal", () => {
      setup();

      fireEvent.click(screen.getByRole("button", { name: "Show info" }));
      fireEvent.click(screen.getByRole("button", { name: "Close info modal" }));

      expect(
        screen.queryByRole("dialog", { name: "Movie info modal" }),
      ).not.toBeInTheDocument();
    });

    it("hides the info modal when the deck moves to another candidate", () => {
      const { rerender, deck } = setup();

      fireEvent.click(screen.getByRole("button", { name: "Show info" }));

      expect(
        screen.getByRole("dialog", { name: "Movie info modal" }),
      ).toBeInTheDocument();

      mockedUseSwipeDeck.mockReturnValue({
        ...deck,
        candidateId: "candidate-2",
        movie: { tmdb_id: 680, title: "Pulp Fiction" },
      } as unknown as Deck);

      rerender(<DiscoverSessionScreen />);

      expect(
        screen.queryByRole("dialog", { name: "Movie info modal" }),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("card-candidate")).toHaveTextContent(
        "candidate-2",
      );
    });
  });

  describe("end session modal", () => {
    it("opens the modal and clears any previous error", () => {
      setup();

      expect(
        screen.queryByRole("dialog", { name: "End session modal" }),
      ).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /End session/i }));

      expect(
        screen.getByRole("dialog", { name: "End session modal" }),
      ).toBeInTheDocument();
      expect(endSession.clearEndSessionError).toHaveBeenCalledTimes(1);
    });

    it("passes the end-session state and error to the modal", () => {
      endSession = createEndSession({
        isEndingSession: true,
        endSessionError: "Could not end the session.",
      });
      mockedUseEndSwipeSession.mockReturnValue(
        endSession as unknown as ReturnType<typeof useEndSwipeSession>,
      );

      setup();

      fireEvent.click(screen.getByRole("button", { name: /End session/i }));

      expect(screen.getByTestId("ending-state")).toHaveTextContent("true");
      expect(screen.getByText("Could not end the session.")).toBeInTheDocument();
    });

    it("closes the modal and clears the error", () => {
      setup();

      fireEvent.click(screen.getByRole("button", { name: /End session/i }));
      fireEvent.click(screen.getByRole("button", { name: "Close end modal" }));

      expect(
        screen.queryByRole("dialog", { name: "End session modal" }),
      ).not.toBeInTheDocument();
      expect(endSession.clearEndSessionError).toHaveBeenCalledTimes(2);
    });

    it("does not close the modal while the session is ending", () => {
      endSession = createEndSession({ isEndingSession: true });
      mockedUseEndSwipeSession.mockReturnValue(
        endSession as unknown as ReturnType<typeof useEndSwipeSession>,
      );

      setup();

      fireEvent.click(screen.getByRole("button", { name: /End session/i }));
      fireEvent.click(screen.getByRole("button", { name: "Close end modal" }));

      expect(
        screen.getByRole("dialog", { name: "End session modal" }),
      ).toBeInTheDocument();
      expect(endSession.clearEndSessionError).toHaveBeenCalledTimes(1);
    });

    it("wires the go home and download actions", () => {
      setup();

      fireEvent.click(screen.getByRole("button", { name: /End session/i }));
      fireEvent.click(screen.getByRole("button", { name: "Go home" }));
      fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));

      expect(endSession.handleGoHome).toHaveBeenCalledTimes(1);
      expect(endSession.handleDownloadCsv).toHaveBeenCalledTimes(1);
    });
  });

  describe("error and terminal states", () => {
    it("renders a not found screen when the session does not exist", () => {
      setup({ sessionNotFound: true });

      expect(
        screen.getByText(
          "This swipe session does not exist or is no longer available.",
        ),
      ).toBeInTheDocument();
      expect(screen.getByText("Back to home")).toBeInTheDocument();
      expect(screen.queryByTestId("swipe-movie-card")).not.toBeInTheDocument();
    });

    it("renders an already finished screen for individual sessions", () => {
      setup({ sessionFinished: true });

      expect(
        screen.getByText("This swipe session has already finished."),
      ).toBeInTheDocument();
      expect(screen.getByText("Back to home")).toBeInTheDocument();
    });

    it("renders the deck error with a retry action", () => {
      const { deck } = setup({ error: "Could not load movies." });

      expect(screen.getByText("Could not load movies.")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Retry" }));

      expect(deck.retry).toHaveBeenCalledTimes(1);
    });

    it("prefers the ended screen over the deck error when the partner ended the session", () => {
      setup({ error: "Could not load movies." }, createPaired({ ended: true }));

      expect(screen.getByText("Session ended")).toBeInTheDocument();
      expect(
        screen.queryByText("Could not load movies."),
      ).not.toBeInTheDocument();
    });
  });

  describe("finished view", () => {
    it("renders the no more recommendations screen", () => {
      setup({ finished: true });

      expect(
        screen.getByRole("heading", { name: "No more recommendations" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "You've gone through all the movies currently available.",
        ),
      ).toBeInTheDocument();
      expect(screen.queryByTestId("swipe-movie-card")).not.toBeInTheDocument();
      expect(screen.queryByTestId("swipe-action-bar")).not.toBeInTheDocument();
    });

    it("opens the end session modal from the finished screen", () => {
      setup({ finished: true });

      fireEvent.click(screen.getByRole("button", { name: /End session/i }));

      expect(
        screen.getByRole("dialog", { name: "End session modal" }),
      ).toBeInTheDocument();
      expect(endSession.clearEndSessionError).toHaveBeenCalledTimes(1);
    });

    it("renders the paired overlay on the finished screen of a paired session", () => {
      setup({ finished: true }, createPaired());

      expect(screen.getByTestId("paired-overlay")).toBeInTheDocument();
    });
  });

  describe("ended by partner", () => {
    it("renders the ended screen when the paired session has ended", () => {
      setup({}, createPaired({ ended: true }));

      expect(
        screen.getByRole("heading", { name: "Session ended" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "This session is over. You can still download your watchlist.",
        ),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Get my watchlist/i }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /^End session$/i }),
      ).not.toBeInTheDocument();
    });

    it("renders the ended screen when the deck reports a finished paired session", () => {
      setup({ sessionFinished: true }, createPaired({ ended: false }));

      expect(
        screen.getByRole("heading", { name: "Session ended" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByText("This swipe session has already finished."),
      ).not.toBeInTheDocument();
    });

    it("opens the end session modal from the get my watchlist button", () => {
      setup({}, createPaired({ ended: true }));

      fireEvent.click(
        screen.getByRole("button", { name: /Get my watchlist/i }),
      );

      expect(
        screen.getByRole("dialog", { name: "End session modal" }),
      ).toBeInTheDocument();
    });

    it("renders the paired overlay on the ended screen", () => {
      setup({}, createPaired({ ended: true }));

      expect(screen.getByTestId("paired-overlay")).toBeInTheDocument();
    });

    it("still shows not found before the ended screen", () => {
      setup({ sessionNotFound: true }, createPaired({ ended: true }));

      expect(
        screen.getByText(
          "This swipe session does not exist or is no longer available.",
        ),
      ).toBeInTheDocument();
      expect(screen.queryByText("Session ended")).not.toBeInTheDocument();
    });
  });
});