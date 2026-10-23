import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
} from "@testing-library/react";
import type { ReactNode } from "react";
import "@testing-library/jest-dom/vitest";

import MatchesModal from "./MatchesModal";
import {
  getSessionMatches,
  type SessionMatch,
} from "../../services/swipeSessions";
import { getErrorMessage } from "../../utils/errors";
import { letterboxdUrl } from "../../utils/movie";

vi.mock("../../services/swipeSessions", () => ({
  getSessionMatches: vi.fn(),
}));

vi.mock("../../utils/errors", () => ({
  getErrorMessage: vi.fn(),
}));

vi.mock("../../utils/movie", () => ({
  letterboxdUrl: vi.fn(
    (tmdbId: number) => `https://letterboxd.com/tmdb/${tmdbId}`,
  ),
}));

vi.mock("./Modal", () => ({
  default: ({
    title,
    children,
    onClose,
  }: {
    title: string;
    children: ReactNode;
    onClose: () => void;
  }) => (
    <div role="dialog" aria-label={title}>
      <button
        type="button"
        onClick={onClose}
        aria-label="Close modal"
      >
        Close
      </button>
      {children}
    </div>
  ),
}));

const mockedGetSessionMatches = vi.mocked(getSessionMatches);
const mockedGetErrorMessage = vi.mocked(getErrorMessage);
const mockedLetterboxdUrl = vi.mocked(letterboxdUrl);

const createMatch = (
  overrides: Partial<SessionMatch> = {},
): SessionMatch => ({
  candidate_id: "101",
  matched_at: "2026-10-22T12:00:00Z",
  movie: {
    tmdb_id: 550,
    title: "Fight Club",
    release_year: 1999,
    poster_url: "https://example.com/fight-club.jpg",
  },
  ...overrides,
});

describe("MatchesModal", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the modal title and loading indicator while fetching", () => {
    mockedGetSessionMatches.mockReturnValue(new Promise(() => {}));

    render(<MatchesModal sessionId="session-1" onClose={vi.fn()} />);

    expect(
      screen.getByRole("dialog", { name: "Your matches" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("dialog").querySelector(".animate-spin"),
    ).toBeInTheDocument();

    expect(mockedGetSessionMatches).toHaveBeenCalledWith("session-1");
  });

  it("renders the empty state when there are no matches", async () => {
    mockedGetSessionMatches.mockResolvedValue([]);

    render(<MatchesModal sessionId="session-1" onClose={vi.fn()} />);

    expect(
      await screen.findByText(/Nothing in common\. Yet\./i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("renders a match with its title, year, poster, and Letterboxd link", async () => {
    mockedGetSessionMatches.mockResolvedValue([createMatch()]);
    mockedLetterboxdUrl.mockReturnValue(
      "https://letterboxd.com/film/fight-club/",
    );

    render(<MatchesModal sessionId="session-1" onClose={vi.fn()} />);

    expect(await screen.findByText("Fight Club")).toBeInTheDocument();
    expect(screen.getByText("1999")).toBeInTheDocument();

    const poster = screen.getByRole("img", {
      name: "Fight Club poster",
    });

    expect(poster).toHaveAttribute(
      "src",
      "https://example.com/fight-club.jpg",
    );

    const link = screen.getByRole("link", { name: /Letterboxd/i });

    expect(link).toHaveAttribute(
      "href",
      "https://letterboxd.com/film/fight-club/",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");

    expect(mockedLetterboxdUrl).toHaveBeenCalledWith(550);
  });

  it("renders multiple matches", async () => {
    mockedGetSessionMatches.mockResolvedValue([
      createMatch(),
      {
        ...createMatch(),
        candidate_id: "202",
        movie: {
          tmdb_id: 680,
          title: "Pulp Fiction",
          release_year: 1994,
          poster_url: "https://example.com/pulp-fiction.jpg",
        },
      },
    ]);

    render(<MatchesModal sessionId="session-1" onClose={vi.fn()} />);

    expect(await screen.findByText("Fight Club")).toBeInTheDocument();
    expect(screen.getByText("Pulp Fiction")).toBeInTheDocument();

    expect(
      screen.getAllByRole("link", { name: /Letterboxd/i }),
    ).toHaveLength(2);
  });

  it("does not render the year when release_year is missing", async () => {
    const match = createMatch({
      movie: {
        ...createMatch().movie,
        release_year: null,
      },
    });

    mockedGetSessionMatches.mockResolvedValue([match]);

    render(<MatchesModal sessionId="session-1" onClose={vi.fn()} />);

    expect(await screen.findByText("Fight Club")).toBeInTheDocument();
    expect(screen.queryByText("1999")).not.toBeInTheDocument();
  });

  it("renders a placeholder when the movie has no poster", async () => {
    const match = createMatch({
      movie: {
        ...createMatch().movie,
        poster_url: "",
      },
    });

    mockedGetSessionMatches.mockResolvedValue([match]);

    render(<MatchesModal sessionId="session-1" onClose={vi.fn()} />);

    expect(await screen.findByText("Fight Club")).toBeInTheDocument();

    expect(
      screen.queryByRole("img", { name: "Fight Club poster" }),
    ).not.toBeInTheDocument();
  });

  it("renders an error when fetching matches fails", async () => {
    mockedGetSessionMatches.mockRejectedValue(
      new Error("Request failed"),
    );
    mockedGetErrorMessage.mockReturnValue("Could not load matches.");

    render(<MatchesModal sessionId="session-1" onClose={vi.fn()} />);

    expect(
      await screen.findByText("Could not load matches."),
    ).toBeInTheDocument();

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Nothing in common\. Yet\./i),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByRole("dialog")?.querySelector(".animate-spin"),
    ).not.toBeInTheDocument();

    expect(mockedGetErrorMessage).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Request failed" }),
    );
  });

  it("refetches matches when sessionId changes", async () => {
    mockedGetSessionMatches
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([createMatch()]);

    const { rerender } = render(
      <MatchesModal sessionId="session-1" onClose={vi.fn()} />,
    );

    expect(
      await screen.findByText(/Nothing in common\. Yet\./i),
    ).toBeInTheDocument();

    rerender(
      <MatchesModal sessionId="session-2" onClose={vi.fn()} />,
    );

    expect(await screen.findByText("Fight Club")).toBeInTheDocument();

    expect(mockedGetSessionMatches).toHaveBeenNthCalledWith(
      1,
      "session-1",
    );
    expect(mockedGetSessionMatches).toHaveBeenNthCalledWith(
      2,
      "session-2",
    );
  });

  it("does not update state after unmount when the request resolves", async () => {
    let resolveRequest!: (
      value: Awaited<ReturnType<typeof getSessionMatches>>,
    ) => void;

    mockedGetSessionMatches.mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );

    const { unmount } = render(
      <MatchesModal sessionId="session-1" onClose={vi.fn()} />,
    );

    unmount();

    resolveRequest([createMatch()]);

    await waitFor(() => {
      expect(mockedGetSessionMatches).toHaveBeenCalledWith("session-1");
    });
  });

  it("calls onClose when the modal close control is clicked", () => {
    mockedGetSessionMatches.mockReturnValue(new Promise(() => {}));

    const onClose = vi.fn();

    render(<MatchesModal sessionId="session-1" onClose={onClose} />);

    screen.getByRole("button", { name: "Close matches" }).click();

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});