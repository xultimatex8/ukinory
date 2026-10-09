const API_URL = import.meta.env.VITE_API_URL || "";

const BACKEND_PREFIXES = ["/api", "/health"];

export function apiUrl(input: RequestInfo | URL): RequestInfo | URL {
  if (
    import.meta.env.PROD &&
    typeof input === "string" &&
    BACKEND_PREFIXES.some((prefix) => input.startsWith(prefix))
  ) {
    if (!API_URL) {
      throw new Error("VITE_API_URL is not configured.");
    }

    return `${API_URL}${input}`;
  }

  return input;
}