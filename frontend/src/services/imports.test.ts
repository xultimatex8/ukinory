
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch } from "./api";
import { importExport } from "./imports";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();

  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

const mockedApiFetch = vi.mocked(apiFetch);

function mockJsonResponse(data: unknown): Response {
  return {
    json: vi.fn().mockResolvedValue(data),
  } as unknown as Response;
}

function makeJobStatus(
  status: "pending" | "running" | "succeeded" | "failed",
  extra: Record<string, unknown> = {},
) {
  return {
    job_id: 123,
    status,
    created_at: "2026-01-01T12:00:00Z",
    started_at: null,
    finished_at: null,
    ...extra,
  };
}

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-01-01T12:00:00Z"));
  vi.resetAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("importExport", () => {
  it("uploads a single ZIP using the file field and returns missing items", async () => {
    const zipFile = new File(["zip contents"], "export.ZIP", {
      type: "application/zip",
    });

    mockedApiFetch
      .mockResolvedValueOnce(
        mockJsonResponse({
          job_id: 123,
          status: "pending",
          status_url: "/api/imports/jobs/123/",
        }),
      )
      .mockResolvedValueOnce(
        mockJsonResponse(
          makeJobStatus("succeeded", {
            result: { missing: ["Movie A", "Movie B"] },
          }),
        ),
      );

    const onStatusChange = vi.fn();
    const promise = importExport([zipFile], onStatusChange);

    await flushPromises();

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      "/api/imports/letterboxd/",
      expect.objectContaining({
        method: "POST",
        body: expect.any(FormData),
      }),
    );

    const formData = mockedApiFetch.mock.calls[0][1]?.body as FormData;
    expect(formData.get("file")).toBe(zipFile);
    expect(formData.getAll("files")).toHaveLength(0);

    await vi.advanceTimersByTimeAsync(3000);

    await expect(promise).resolves.toEqual({
      missing: ["Movie A", "Movie B"],
    });

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      "/api/imports/jobs/123/",
    );
    expect(onStatusChange).toHaveBeenNthCalledWith(1, "pending");
    expect(onStatusChange).toHaveBeenNthCalledWith(2, "succeeded");
  });

  it("uploads multiple files using the files field", async () => {
    const csvFile = new File(["date,rating"], "diary.csv", {
      type: "text/csv",
    });
    const watchedFile = new File(["watched"], "watched.html", {
      type: "text/html",
    });

    mockedApiFetch
      .mockResolvedValueOnce(
        mockJsonResponse({
          job_id: 456,
          status: "running",
          status_url: "/api/imports/jobs/456/",
        }),
      )
      .mockResolvedValueOnce(
        mockJsonResponse(makeJobStatus("succeeded", { result: { missing: [] } })),
      );

    const promise = importExport([csvFile, watchedFile]);

    await flushPromises();

    const formData = mockedApiFetch.mock.calls[0][1]?.body as FormData;
    expect(formData.get("file")).toBeNull();
    expect(formData.getAll("files")).toEqual([csvFile, watchedFile]);

    await vi.advanceTimersByTimeAsync(3000);

    await expect(promise).resolves.toEqual({ missing: [] });
  });

  it("uploads a single non-ZIP file using the files field", async () => {
    const csvFile = new File(["title"], "watchlist.csv", {
      type: "text/csv",
    });

    mockedApiFetch
      .mockResolvedValueOnce(
        mockJsonResponse({
          job_id: 789,
          status: "pending",
          status_url: "/api/imports/jobs/789/",
        }),
      )
      .mockResolvedValueOnce(
        mockJsonResponse(makeJobStatus("succeeded")),
      );

    const promise = importExport([csvFile]);

    await flushPromises();

    const formData = mockedApiFetch.mock.calls[0][1]?.body as FormData;
    expect(formData.get("file")).toBeNull();
    expect(formData.getAll("files")).toEqual([csvFile]);

    await vi.advanceTimersByTimeAsync(3000);

    await expect(promise).resolves.toEqual({ missing: [] });
  });

  it("reports each status while the job is pending and running", async () => {
    const file = new File(["data"], "export.zip");

    mockedApiFetch
      .mockResolvedValueOnce(
        mockJsonResponse({
          job_id: 1,
          status: "pending",
          status_url: "/jobs/1/",
        }),
      )
      .mockResolvedValueOnce(
        mockJsonResponse(makeJobStatus("running")),
      )
      .mockResolvedValueOnce(
        mockJsonResponse(
          makeJobStatus("succeeded", {
            result: { missing: ["Unknown Movie"] },
          }),
        ),
      );

    const onStatusChange = vi.fn();
    const promise = importExport([file], onStatusChange);

    await flushPromises();
    expect(onStatusChange).toHaveBeenNthCalledWith(1, "pending");

    await vi.advanceTimersByTimeAsync(3000);
    expect(onStatusChange).toHaveBeenNthCalledWith(2, "running");

    await vi.advanceTimersByTimeAsync(3000);

    await expect(promise).resolves.toEqual({
      missing: ["Unknown Movie"],
    });
    expect(onStatusChange).toHaveBeenNthCalledWith(3, "succeeded");
  });

  it("returns an empty missing list when the successful result omits it", async () => {
    mockedApiFetch
      .mockResolvedValueOnce(
        mockJsonResponse({
          job_id: 2,
          status: "pending",
          status_url: "/jobs/2/",
        }),
      )
      .mockResolvedValueOnce(
        mockJsonResponse(makeJobStatus("succeeded")),
      );

    const promise = importExport([
      new File(["data"], "export.zip"),
    ]);

    await flushPromises();
    await vi.advanceTimersByTimeAsync(3000);

    await expect(promise).resolves.toEqual({ missing: [] });
  });

  it("throws ApiError when the job fails with an error message", async () => {
    mockedApiFetch
      .mockResolvedValueOnce(
        mockJsonResponse({
          job_id: 3,
          status: "pending",
          status_url: "/jobs/3/",
        }),
      )
      .mockResolvedValueOnce(
        mockJsonResponse(
          makeJobStatus("failed", { error: "Invalid export file" }),
        ),
      );

    const promise = importExport([
      new File(["data"], "export.zip"),
    ]);

    await flushPromises();
    const assertion = expect(promise).rejects.toMatchObject({
      name: "ApiError",
      status: 500,
      detail: "Invalid export file",
    });

    await vi.advanceTimersByTimeAsync(3000);
    await assertion;
  });

  it("uses a default message when the failed job has no error message", async () => {
    mockedApiFetch
      .mockResolvedValueOnce(
        mockJsonResponse({
          job_id: 4,
          status: "pending",
          status_url: "/jobs/4/",
        }),
      )
      .mockResolvedValueOnce(
        mockJsonResponse(makeJobStatus("failed")),
      );

    const promise = importExport([
      new File(["data"], "export.zip"),
    ]);

    await flushPromises();
    const assertion = expect(promise).rejects.toMatchObject({
      status: 500,
      detail: "The import failed.",
    });

    await vi.advanceTimersByTimeAsync(3000);
    await assertion;
  });

  it("times out when the job does not finish before the deadline", async () => {
    mockedApiFetch
      .mockResolvedValueOnce(
        mockJsonResponse({
          job_id: 5,
          status: "pending",
          status_url: "/jobs/5/",
        }),
      )
      .mockImplementation(async () =>
        mockJsonResponse(makeJobStatus("running")),
      );

    const promise = importExport([
      new File(["data"], "export.zip"),
    ]);

    await flushPromises();

    const assertion = expect(promise).rejects.toMatchObject({
      name: "ApiError",
      status: 504,
      detail:
        "The import is taking longer than expected. It's still running in " +
        "the background -- check back in a bit.",
    });

    await vi.advanceTimersByTimeAsync(15 * 60 * 1000);
    await assertion;
  });

  it("propagates errors from the initial upload request", async () => {
    const error = new ApiError(400, "Invalid upload");
    mockedApiFetch.mockRejectedValueOnce(error);

    await expect(
      importExport([new File(["data"], "export.zip")]),
    ).rejects.toBe(error);

    expect(mockedApiFetch).toHaveBeenCalledTimes(1);
  });

  it("supports calling importExport without a status callback", async () => {
    mockedApiFetch
      .mockResolvedValueOnce(
        mockJsonResponse({
          job_id: 6,
          status: "pending",
          status_url: "/jobs/6/",
        }),
      )
      .mockResolvedValueOnce(
        mockJsonResponse(makeJobStatus("succeeded", {
          result: { missing: ["Movie C"] },
        })),
      );

    const promise = importExport([
      new File(["data"], "export.zip"),
    ]);

    await flushPromises();
    await vi.advanceTimersByTimeAsync(3000);

    await expect(promise).resolves.toEqual({
      missing: ["Movie C"],
    });
  });
});
