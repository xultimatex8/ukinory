
import { describe, expect, it } from "vitest";
import { ApiError } from "../services/api";
import { getErrorMessage } from "./errors";

describe("getErrorMessage", () => {
  describe("when the error is an ApiError", () => {
    it("returns the error detail", () => {
      const error = new ApiError(400, "Invalid request");

      expect(getErrorMessage(error)).toBe("Invalid request");
    });

    it("returns the detail instead of the generic error message", () => {
      const error = new ApiError(403, "Access denied");

      expect(getErrorMessage(error)).toBe("Access denied");
    });

    it("returns an empty detail when the API error detail is empty", () => {
      const error = new ApiError(500, "");

      expect(getErrorMessage(error)).toBe("");
    });
  });

  describe("when the error is a standard Error", () => {
    it("returns the error message", () => {
      const error = new Error("Something went wrong");

      expect(getErrorMessage(error)).toBe("Something went wrong");
    });

    it("returns an empty message when the error message is empty", () => {
      const error = new Error("");

      expect(getErrorMessage(error)).toBe("");
    });

    it("supports TypeError instances", () => {
      const error = new TypeError("Invalid type");

      expect(getErrorMessage(error)).toBe("Invalid type");
    });

    it("supports RangeError instances", () => {
      const error = new RangeError("Value out of range");

      expect(getErrorMessage(error)).toBe("Value out of range");
    });
  });

  describe("when the value is not an Error", () => {
    it("returns the generic message for null", () => {
      expect(getErrorMessage(null)).toBe(
        "An unexpected error occurred.",
      );
    });

    it("returns the generic message for undefined", () => {
      expect(getErrorMessage(undefined)).toBe(
        "An unexpected error occurred.",
      );
    });

    it("returns the generic message for a string", () => {
      expect(getErrorMessage("Something went wrong")).toBe(
        "An unexpected error occurred.",
      );
    });

    it("returns the generic message for a number", () => {
      expect(getErrorMessage(500)).toBe(
        "An unexpected error occurred.",
      );
    });

    it("returns the generic message for a plain object", () => {
      expect(getErrorMessage({ message: "Custom error" })).toBe(
        "An unexpected error occurred.",
      );
    });

    it("returns the generic message for a boolean", () => {
      expect(getErrorMessage(false)).toBe(
        "An unexpected error occurred.",
      );
    });
  });
});