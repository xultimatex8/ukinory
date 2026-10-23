
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { downloadBlob } from "./download";

describe("downloadBlob", () => {
  let createObjectURLSpy: ReturnType<typeof vi.spyOn>;
  let revokeObjectURLSpy: ReturnType<typeof vi.spyOn>;
  let clickSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.useFakeTimers();

    createObjectURLSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:http://localhost/mock-file");

    revokeObjectURLSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => {});

    clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("creates a download link with the provided filename", () => {
    const blob = new Blob(["file contents"], { type: "text/csv" });
    let capturedHref: string | undefined;
    let capturedFilename: string | undefined;

    clickSpy.mockImplementation(function (this: HTMLAnchorElement) {
      capturedHref = this.href;
      capturedFilename = this.download;
    });

    downloadBlob(blob, "watchlist.csv");

    expect(createObjectURLSpy).toHaveBeenCalledWith(blob);
    expect(capturedHref).toBe("blob:http://localhost/mock-file");
    expect(capturedFilename).toBe("watchlist.csv");
  });

  it("clicks the link to trigger the download", () => {
    const blob = new Blob(["file contents"]);

    downloadBlob(blob, "export.csv");

    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it("appends the link to the document before clicking it", () => {
    const blob = new Blob(["file contents"]);
    let wasAttachedDuringClick = false;

    clickSpy.mockImplementation(function (this: HTMLAnchorElement) {
      wasAttachedDuringClick = document.body.contains(this);
    });

    downloadBlob(blob, "export.csv");

    expect(wasAttachedDuringClick).toBe(true);
  });

  it("removes the temporary link after clicking", () => {
    const blob = new Blob(["file contents"]);

    downloadBlob(blob, "export.csv");

    expect(document.querySelector("a")).toBeNull();
  });

  it("revokes the object URL after one second", () => {
    const blob = new Blob(["file contents"]);

    downloadBlob(blob, "export.csv");

    expect(revokeObjectURLSpy).not.toHaveBeenCalled();

    vi.advanceTimersByTime(999);
    expect(revokeObjectURLSpy).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);

    expect(revokeObjectURLSpy).toHaveBeenCalledWith(
      "blob:http://localhost/mock-file",
    );
    expect(revokeObjectURLSpy).toHaveBeenCalledTimes(1);
  });

  it("supports an empty blob", () => {
    const blob = new Blob([]);

    expect(() => downloadBlob(blob, "empty.txt")).not.toThrow();

    expect(createObjectURLSpy).toHaveBeenCalledWith(blob);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(document.querySelector("a")).toBeNull();
  });

  it("supports filenames containing spaces and extensions", () => {
    const blob = new Blob(["data"]);
    let capturedFilename: string | undefined;

    clickSpy.mockImplementation(function (this: HTMLAnchorElement) {
      capturedFilename = this.download;
    });

    downloadBlob(blob, "My movie watchlist.csv");

    expect(capturedFilename).toBe("My movie watchlist.csv");
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });
});