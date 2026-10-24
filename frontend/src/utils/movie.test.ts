
import { describe, expect, it } from "vitest";
import { formatRuntime, letterboxdUrl } from "./movie";

describe("formatRuntime", () => {
  it("formats a runtime shorter than one hour", () => {
    expect(formatRuntime(45)).toBe("0h 45 min");
  });

  it("formats a runtime of exactly one hour", () => {
    expect(formatRuntime(60)).toBe("1h 0 min");
  });

  it("formats a runtime longer than one hour", () => {
    expect(formatRuntime(125)).toBe("2h 5 min");
  });

  it("formats a runtime of multiple hours with no remaining minutes", () => {
    expect(formatRuntime(180)).toBe("3h 0 min");
  });

  it("formats zero minutes", () => {
    expect(formatRuntime(0)).toBe("0h 0 min");
  });

  it("formats a runtime of one minute", () => {
    expect(formatRuntime(1)).toBe("0h 1 min");
  });

  it("formats a runtime of 59 minutes", () => {
    expect(formatRuntime(59)).toBe("0h 59 min");
  });

  it("preserves the remainder for runtimes over several hours", () => {
    expect(formatRuntime(367)).toBe("6h 7 min");
  });

  it("uses floor for fractional hours", () => {
    expect(formatRuntime(90.5)).toBe("1h 30.5 min");
  });

  it("handles negative values according to JavaScript arithmetic", () => {
    expect(formatRuntime(-30)).toBe("-1h -30 min");
  });
});

describe("letterboxdUrl", () => {
  it("builds a URL from a numeric TMDB ID", () => {
    expect(letterboxdUrl(550)).toBe(
      "https://letterboxd.com/tmdb/550",
    );
  });

  it("builds a URL from a string TMDB ID", () => {
    expect(letterboxdUrl("550")).toBe(
      "https://letterboxd.com/tmdb/550",
    );
  });

  it("encodes special characters in a string ID", () => {
    expect(letterboxdUrl("movie id/123")).toBe(
      "https://letterboxd.com/tmdb/movie%20id%2F123",
    );
  });

  it("encodes spaces and query characters", () => {
    expect(letterboxdUrl("123?foo=bar")).toBe(
      "https://letterboxd.com/tmdb/123%3Ffoo%3Dbar",
    );
  });

  it("handles an empty string ID", () => {
    expect(letterboxdUrl("")).toBe(
      "https://letterboxd.com/tmdb/",
    );
  });

  it("handles a numeric ID of zero", () => {
    expect(letterboxdUrl(0)).toBe(
      "https://letterboxd.com/tmdb/0",
    );
  });
});