import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import RateMovieModal from "./RateMovieModal";
import { ApiError } from "../../services/api";
import { rateMovie } from "../../services/library";

vi.mock("../../services/library", () => ({
  rateMovie: vi.fn(),
}));

vi.mock("lucide-react", () => ({
  Heart: () => <svg data-testid="heart-icon" />,
  Loader2: () => <svg data-testid="loader-icon" />,
  Star: () => <svg data-testid="star-icon" />,
  X: () => <svg data-testid="close-icon" />,
}));

const mockedRateMovie = vi.mocked(rateMovie);

describe("RateMovieModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the movie title and rating controls", () => {
    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Mark as watched" })).toBeInTheDocument();
    expect(screen.getByText("Fight Club")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Like this" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();

    for (const label of [
      "0.5 stars",
      "1 star",
      "1.5 stars",
      "2 stars",
      "2.5 stars",
      "3 stars",
      "3.5 stars",
      "4 stars",
      "4.5 stars",
      "5 stars",
    ]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("selects a full-star rating", () => {
    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "4 stars" }));
    mockedRateMovie.mockResolvedValue(undefined);

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(mockedRateMovie).toHaveBeenCalledWith(
      550,
      expect.objectContaining({ rating: 4, liked: false }),
    );
  });

  it("selects a half-star rating", async () => {
    const onSaved = vi.fn();
    mockedRateMovie.mockResolvedValue(undefined);

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={onSaved}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "3.5 stars" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockedRateMovie).toHaveBeenCalledWith(
        550,
        expect.objectContaining({ rating: 3.5, liked: false }),
      );
    });

    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it("clears the selected rating when the same value is clicked again", async () => {
    mockedRateMovie.mockResolvedValue(undefined);

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "4 stars" }));
    fireEvent.click(screen.getByRole("button", { name: "4 stars" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockedRateMovie).toHaveBeenCalledWith(
        550,
        expect.objectContaining({ rating: null, liked: false }),
      );
    });
  });

  it("toggles the liked state", async () => {
    mockedRateMovie.mockResolvedValue(undefined);

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Like this" }));

    expect(screen.getByRole("button", { name: "Liked" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockedRateMovie).toHaveBeenCalledWith(
        550,
        expect.objectContaining({ liked: true }),
      );
    });
  });

  it("sends the current date in YYYY-MM-DD format", async () => {
    mockedRateMovie.mockResolvedValue(undefined);

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(mockedRateMovie).toHaveBeenCalledTimes(1);
    });

    const [, payload] = mockedRateMovie.mock.calls[0];

    expect(payload.watched_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("calls onSaved when saving succeeds", async () => {
    const onSaved = vi.fn();
    mockedRateMovie.mockResolvedValue(undefined);

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={onSaved}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledTimes(1);
    });

    expect(mockedRateMovie).toHaveBeenCalledWith(
      550,
      expect.objectContaining({
        rating: null,
        liked: false,
        watched_date: expect.any(String),
      }),
    );
  });

  it("shows an API error message when saving fails with ApiError", async () => {
    mockedRateMovie.mockRejectedValue(
      new ApiError(400, "Rating could not be saved"),
    );

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("Rating could not be saved"),
    ).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  it("shows a fallback message when saving fails with a generic error", async () => {
    mockedRateMovie.mockRejectedValue(new Error("Network error"));

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("Couldn't save this. Try again."),
    ).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  it("disables controls and shows a loader while saving", async () => {
    let resolveRequest!: () => void;

    mockedRateMovie.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveRequest = resolve;
      }),
    );

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByTestId("loader-icon")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Like this" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "1 star" })).toBeDisabled();

    resolveRequest();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={onClose}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when Cancel is clicked", () => {
    const onClose = vi.fn();

    render(
      <RateMovieModal
        movieId={550}
        movieTitle="Fight Club"
        onClose={onClose}
        onSaved={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});