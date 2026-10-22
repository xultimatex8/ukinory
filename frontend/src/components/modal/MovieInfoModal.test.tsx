import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import MovieInfoModal from "./MovieInfoModal";
import type { MovieRecommendation } from "../../services/swipeSessions";
import type { StreamingCountry } from "../StreamingProviders";

const movie: MovieRecommendation = {
  tmdb_id: 550,
  title: "Fight Club",
  release_year: 1999,
  runtime: 139,
  vote_average: 8.4,
  poster_url: "",
  genres: [
    { tmdb_id: 18, name: "Drama" },
    { tmdb_id: 53, name: "Thriller" },
  ],
  synopsis: "An insomniac office worker meets a soap salesman.",
  streaming_providers: {},
};

const streamingCountries: StreamingCountry[] = [
  {
    code: "ES",
    name: "Spain",
    providers: [
      {
        id: 8,
        name: "Netflix",
        logoUrl: "https://example.com/netflix.jpg",
      },
      {
        id: 119,
        name: "Amazon Prime Video",
        logoUrl: "https://example.com/prime.jpg",
      },
    ],
  },
  {
    code: "US",
    name: "United States",
    providers: [
      {
        id: 337,
        name: "Disney Plus",
        logoUrl: "https://example.com/disney.jpg",
      },
    ],
  },
];

describe("MovieInfoModal", () => {
  beforeEach(() => {
    HTMLDialogElement.prototype.showModal = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.setAttribute("open", "");
    });

    HTMLDialogElement.prototype.close = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.removeAttribute("open");
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders the movie title and basic information", () => {
    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Movie information" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fight Club" })).toBeInTheDocument();
    expect(screen.getByText("1999")).toBeInTheDocument();
    expect(screen.getByText("2h 19 min")).toBeInTheDocument();
    expect(screen.getByText("8.4")).toBeInTheDocument();
  });

  it("opens the native dialog on mount", () => {
    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={vi.fn()}
      />,
    );

    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledTimes(1);
    expect(document.querySelector("dialog")).toHaveAttribute("open");
  });

  it("closes the dialog on unmount", () => {
    const { unmount } = render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={vi.fn()}
      />,
    );

    const dialog = document.querySelector("dialog")!;

    unmount();

    expect(HTMLDialogElement.prototype.close).toHaveBeenCalledTimes(1);
    expect(dialog).not.toHaveAttribute("open");
  });

  it("renders genres and the synopsis", () => {
    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Drama")).toBeInTheDocument();
    expect(screen.getByText("Thriller")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Synopsis" })).toBeInTheDocument();
    expect(
      screen.getByText("An insomniac office worker meets a soap salesman."),
    ).toBeInTheDocument();
  });

  it("renders the default Spanish streaming providers", () => {
    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("img", { name: "Netflix" })).toHaveAttribute(
      "src",
      "https://example.com/netflix.jpg",
    );
    expect(screen.getByRole("img", { name: "Amazon Prime Video" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Disney Plus" })).not.toBeInTheDocument();
  });

  it("changes the streaming providers when another country is selected", () => {
    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole("combobox", { name: "Select country" }), {
      target: { value: "US" },
    });

    expect(screen.getByRole("img", { name: "Disney Plus" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Netflix" })).not.toBeInTheDocument();
  });

  it("uses the first country when Spain is not available", () => {
    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={[streamingCountries[1]]}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("combobox", { name: "Select country" })).toHaveValue("US");
    expect(screen.getByRole("img", { name: "Disney Plus" })).toBeInTheDocument();
  });

  it("renders a message when there are no countries or providers", () => {
    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={[]}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByRole("combobox", { name: "Select country" })).not.toBeInTheDocument();
    expect(screen.getByText("No streaming information available.")).toBeInTheDocument();
    expect(screen.getByText(/JustWatch/)).toBeInTheDocument();
  });

  it("renders the Letterboxd link with the movie TMDB id", () => {
    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={vi.fn()}
      />,
    );

    const link = screen.getByRole("link", { name: "View on Letterboxd" });

    expect(link).toHaveAttribute("href", "https://letterboxd.com/tmdb/550");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();

    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();

    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={onClose}
      />,
    );

    const dialog = document.querySelector("dialog")!;
    fireEvent.click(dialog);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not call onClose when clicking inside the modal", () => {
    const onClose = vi.fn();

    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByRole("heading", { name: "Fight Club" }));

    expect(onClose).not.toHaveBeenCalled();
  });

  it("prevents the default cancel behavior and calls onClose", () => {
    const onClose = vi.fn();

    render(
      <MovieInfoModal
        movie={movie}
        streamingCountries={streamingCountries}
        onClose={onClose}
      />,
    );

    const dialog = document.querySelector("dialog")!;
    const event = new Event("cancel", { cancelable: true });

    fireEvent(dialog, event);

    expect(event.defaultPrevented).toBe(true);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("omits optional movie details when they are absent", () => {
    const movieWithoutOptionalDetails = {
      ...movie,
      release_year: 0,
      runtime: 0,
      vote_average: null,
      genres: [],
      synopsis: "",
    };

    render(
      <MovieInfoModal
        movie={movieWithoutOptionalDetails}
        streamingCountries={[]}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Fight Club" })).toBeInTheDocument();
    expect(screen.queryByText("1999")).not.toBeInTheDocument();
    expect(screen.queryByText("2h 19 min")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Synopsis" })).not.toBeInTheDocument();
    expect(screen.queryByText("Drama")).not.toBeInTheDocument();
  });
});