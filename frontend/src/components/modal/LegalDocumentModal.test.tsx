import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import LegalDocumentModal from "./LegalDocumentModal";
import type { LegalDocument, LegalDocumentType } from "../../services/legal";

vi.mock("motion/react", () => ({
  motion: {
    div: ({
      children,
      ...props
    }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
  },
}));

const documents: LegalDocument[] = [
  {
    id: "terms-1",
    type: "TERMS",
    version: "1.2",
    effective_at: "2026-01-15T00:00:00Z",
    content: `# Terms and Conditions

Welcome to **Ukinory**.

## Using the service

- Follow the rules.
- Respect other users.

[Internal link](/help)

[External link](https://example.com/terms)
`,
  },
  {
    id: "privacy-1",
    type: "PRIVACY",
    version: "2.0",
    effective_at: "2026-02-01T00:00:00Z",
    content: `# Privacy Policy

We respect your privacy.

## Your data

Your data is handled carefully.
`,
  },
];

describe("LegalDocumentModal", () => {
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

  const renderModal = (
    initialType: LegalDocumentType = "TERMS",
    onClose = vi.fn(),
    docs: LegalDocument[] = documents,
  ) => {
    return {
      onClose,
      ...render(
        <LegalDocumentModal
          documents={docs}
          initialType={initialType}
          onClose={onClose}
        />,
      ),
    };
  };

  it("renders the terms document by default", () => {
    renderModal();

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Terms and Conditions",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Version 1\.2/)).toBeInTheDocument();
    expect(screen.getByText(/Welcome to/)).toBeInTheDocument();
    expect(screen.getByText("Ukinory")).toBeInTheDocument();
  });

  it("renders the privacy policy when initialType is PRIVACY", () => {
    renderModal("PRIVACY");

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Privacy Policy",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Version 2\.0/)).toBeInTheDocument();
    expect(screen.getByText("We respect your privacy.")).toBeInTheDocument();
  });

  it("opens the native dialog on mount", () => {
    renderModal();

    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledTimes(1);
    expect(document.querySelector("dialog")).toHaveAttribute("open");
  });

  it("closes the dialog on unmount", () => {
    const { unmount } = renderModal();
    const dialog = document.querySelector("dialog")!;

    unmount();

    expect(HTMLDialogElement.prototype.close).toHaveBeenCalledTimes(1);
    expect(dialog).not.toHaveAttribute("open");
  });

  it("renders document tabs when multiple documents are available", () => {
    renderModal();

    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Terms and Conditions" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Privacy Policy" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("switches to the privacy policy when its tab is clicked", () => {
    renderModal();

    fireEvent.click(screen.getByRole("tab", { name: "Privacy Policy" }));

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Privacy Policy",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Version 2\.0/)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Privacy Policy" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Terms and Conditions" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("does not render tabs when only one document is available", () => {
    renderModal("TERMS", vi.fn(), [documents[0]]);

    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });

  it("renders Markdown headings, lists and strong text", () => {
    renderModal();

    const content = screen.getByText("Follow the rules.").closest("div");

    expect(screen.getByRole("heading", { name: "Using the service" })).toBeInTheDocument();
    expect(screen.getByText("Ukinory").tagName).toBe("STRONG");
    expect(content?.querySelector("ul")).toBeInTheDocument();
    expect(screen.getByText("Respect other users.")).toBeInTheDocument();
  });

  it("opens external Markdown links in a new tab safely", () => {
    renderModal();

    const link = screen.getByRole("link", { name: "External link" });

    expect(link).toHaveAttribute("href", "https://example.com/terms");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("does not add target blank to internal Markdown links", () => {
    renderModal();

    const link = screen.getByRole("link", { name: "Internal link" });

    expect(link).toHaveAttribute("href", "/help");
    expect(link).not.toHaveAttribute("target");
    expect(link).not.toHaveAttribute("rel");
  });

  it("calls onClose when the header close button is clicked", () => {
    const onClose = vi.fn();
    renderModal("TERMS", onClose);

    fireEvent.click(screen.getAllByRole("button", { name: "Close" })[0]);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the bottom Close button is clicked", () => {
    const onClose = vi.fn();
    renderModal("TERMS", onClose);

    const closeButtons = screen.getAllByRole("button", { name: "Close" });
    fireEvent.click(closeButtons[1]);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    renderModal("TERMS", onClose);

    const dialog = document.querySelector("dialog")!;
    fireEvent.click(dialog);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not close when clicking inside the modal", () => {
    const onClose = vi.fn();
    renderModal("TERMS", onClose);

    const paragraph = screen.getByText((_, element) =>
      element?.tagName === "P" &&
      element.textContent === "Welcome to Ukinory.",
    );

    fireEvent.click(paragraph);

    expect(onClose).not.toHaveBeenCalled();
  });

  it("prevents the default cancel behavior and calls onClose", () => {
    const onClose = vi.fn();
    renderModal("TERMS", onClose);

    const dialog = document.querySelector("dialog")!;
    const event = new Event("cancel", { cancelable: true });

    fireEvent(dialog, event);

    expect(event.defaultPrevented).toBe(true);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when the documents array is empty", () => {
    renderModal("TERMS", vi.fn(), []);

    expect(document.querySelector("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Terms and Conditions" })).not.toBeInTheDocument();
  });
});