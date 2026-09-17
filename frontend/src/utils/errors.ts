import { ApiError } from "../services/api";

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "An unexpected error occurred.";
}