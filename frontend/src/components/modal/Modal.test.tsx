import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import Modal from "./Modal";

describe("Modal", () => {
  beforeEach(() => {
    // jsdom no implementa showModal() y close() de HTMLDialogElement.
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

  it("renders the title and children", () => {
    render(
      <Modal title="Test modal" onClose={vi.fn()}>
        <p>Modal content</p>
      </Modal>,
    );

    expect(
      screen.getAllByRole("dialog", { name: "Test modal" })[1],
    ).toBeInTheDocument();
    expect(screen.getByText("Modal content")).toBeInTheDocument();
  });

  it("opens the native dialog on mount", () => {
    render(
      <Modal title="Test modal" onClose={vi.fn()}>
        Content
      </Modal>,
    );

    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledTimes(1);
    expect(document.querySelector("dialog")).toHaveAttribute("open");
  });

  it("closes the dialog on unmount when it is open", () => {
    const { unmount } = render(
      <Modal title="Test modal" onClose={vi.fn()}>
        Content
      </Modal>,
    );

    const dialog = document.querySelector("dialog")!;

    unmount();

    expect(HTMLDialogElement.prototype.close).toHaveBeenCalledTimes(1);
    expect(dialog).not.toHaveAttribute("open");
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();

    render(
      <Modal title="Test modal" onClose={onClose}>
        Content
      </Modal>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();

    render(
      <Modal title="Test modal" onClose={onClose}>
        Content
      </Modal>,
    );

    const dialog = document.querySelector("dialog")!;

    // Simula un clic directamente sobre el fondo del elemento dialog.
    fireEvent.click(dialog, { target: dialog });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not call onClose when clicking inside the modal content", () => {
    const onClose = vi.fn();

    render(
      <Modal title="Test modal" onClose={onClose}>
        <p>Inner content</p>
      </Modal>,
    );

    fireEvent.click(screen.getByText("Inner content"));

    expect(onClose).not.toHaveBeenCalled();
  });

  it("prevents the default Escape behavior and calls onClose", () => {
    const onClose = vi.fn();

    render(
      <Modal title="Test modal" onClose={onClose}>
        Content
      </Modal>,
    );

    const dialog = document.querySelector("dialog")!;
    const event = new Event("cancel", {
      bubbles: false,
      cancelable: true,
    });

    fireEvent(dialog, event);

    expect(event.defaultPrevented).toBe(true);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("uses the default size when size is omitted", () => {
    render(
      <Modal title="Test modal" onClose={vi.fn()}>
        Content
      </Modal>,
    );

    const dialogs = screen.getAllByRole("dialog", {
      name: "Test modal",
    });

    expect(dialogs[1]).toHaveClass(
      "max-w-2xl",
      "max-h-[90vh]",
    );
  });

  it("applies the large size when size is lg", () => {
    render(
      <Modal title="Test modal" onClose={vi.fn()} size="lg">
        Content
      </Modal>
    );

    const dialogs = screen.getAllByRole("dialog", {
      name: "Test modal",
    });

    expect(dialogs[1]).toHaveClass(
      "max-w-2xl",
      "max-h-[90vh]",
    );
  });

  it("applies the custom title class", () => {
    render(
      <Modal
        title="Test modal"
        onClose={vi.fn()}
        titleClassName="custom-title"
      >
        Content
      </Modal>,
    );

    expect(screen.getByRole("heading", { name: "Test modal" })).toHaveClass(
      "custom-title",
    );
  });
});