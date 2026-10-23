import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import EndSessionModal from "./EndSessionModal";

describe("EndSessionModal", () => {
  const createProps = (
    overrides: Partial<React.ComponentProps<typeof EndSessionModal>> = {},
  ) => ({
    isEndingSession: false,
    error: null,
    onClose: vi.fn(),
    onGoHome: vi.fn(),
    onDownloadCsv: vi.fn(),
    ...overrides,
  });

  it("renders the session-ending title and description", () => {
    render(<EndSessionModal {...createProps()} />);

    expect(
      screen.getByRole("heading", { name: "End session?" }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/You can return home or end the session/i),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/download your watchlist as a CSV file/i),
    ).toBeInTheDocument();
  });

  it("renders both action buttons", () => {
    render(<EndSessionModal {...createProps()} />);

    expect(
      screen.getByRole("button", { name: "Back to home" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Download CSV" }),
    ).toBeInTheDocument();
  });

  it("calls onGoHome when the home action is clicked", () => {
    const props = createProps();
    render(<EndSessionModal {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "Back to home" }));

    expect(props.onGoHome).toHaveBeenCalledTimes(1);
    expect(props.onDownloadCsv).not.toHaveBeenCalled();
  });

  it("calls onDownloadCsv when the download action is clicked", () => {
    const props = createProps();
    render(<EndSessionModal {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    expect(props.onDownloadCsv).toHaveBeenCalledTimes(1);
    expect(props.onGoHome).not.toHaveBeenCalled();
  });

  it("calls onClose when the modal is closed", () => {
    const props = createProps();
    render(<EndSessionModal {...props} />);

    const closeButton =
      screen.queryByRole("button", { name: /close/i }) ??
      screen.queryByRole("button", { name: /cancel/i });

    if (!closeButton) {
      throw new Error("Expected a close or cancel button in ConfirmModal");
    }

    fireEvent.click(closeButton);

    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("displays an error when one is provided", () => {
    render(
      <EndSessionModal
        {...createProps({ error: "Unable to end the session." })}
      />,
    );

    expect(
      screen.getByText("Unable to end the session."),
    ).toBeInTheDocument();
  });

  it("does not display an error when error is null", () => {
    render(<EndSessionModal {...createProps({ error: null })} />);

    expect(
      screen.queryByText("Unable to end the session."),
    ).not.toBeInTheDocument();
  });

  it("shows the loading label while ending the session", () => {
    render(
      <EndSessionModal {...createProps({ isEndingSession: true })} />,
    );

    expect(
      screen.getByRole("button", { name: /Ending session/i }),
    ).toBeInTheDocument();
  });

  it("disables actions while ending the session", () => {
    render(
      <EndSessionModal {...createProps({ isEndingSession: true })} />,
    );

    expect(
      screen.getByRole("button", { name: /Back to home/i }),
    ).toBeDisabled();

    expect(
      screen.getByRole("button", { name: /Ending session/i }),
    ).toBeDisabled();
  });

  it("allows actions when the session is not ending", () => {
    render(<EndSessionModal {...createProps()} />);

    expect(
      screen.getByRole("button", { name: "Back to home" }),
    ).toBeEnabled();

    expect(
      screen.getByRole("button", { name: "Download CSV" }),
    ).toBeEnabled();
  });
});