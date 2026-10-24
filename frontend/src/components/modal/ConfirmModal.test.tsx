import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import ConfirmModal from "./ConfirmModal";

describe("ConfirmModal", () => {
  const createProps = (
    overrides: Partial<React.ComponentProps<typeof ConfirmModal>> = {},
  ) => ({
    title: "Delete account",
    description: "Are you sure you want to continue?",
    error: null,
    onClose: vi.fn(),
    actions: [
      {
        label: "Cancel",
        variant: "secondary" as const,
        onClick: vi.fn(),
      },
      {
        label: "Confirm",
        variant: "danger" as const,
        onClick: vi.fn(),
      },
    ],
    ...overrides,
  });

  it("renders the title, description and actions", () => {
    render(<ConfirmModal {...createProps()} />);

    expect(
      screen.getByRole("heading", { name: "Delete account" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Are you sure you want to continue?"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  });

  it("renders a ReactNode description", () => {
    render(
      <ConfirmModal
        {...createProps({
          description: (
            <span>
              This action is <strong>irreversible</strong>.
            </span>
          ),
        })}
      />,
    );

    expect(screen.getByText("irreversible")).toBeInTheDocument();
  });

  it("renders an error when provided", () => {
    render(
      <ConfirmModal {...createProps({ error: "Something went wrong" })} />,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("does not render an error when error is null", () => {
    render(<ConfirmModal {...createProps({ error: null })} />);

    expect(
      screen.queryByText("Something went wrong"),
    ).not.toBeInTheDocument();
  });

  it("calls the corresponding action when a button is clicked", () => {
    const props = createProps();
    render(<ConfirmModal {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));

    expect(props.actions[0].onClick).toHaveBeenCalledTimes(1);
    expect(props.actions[1].onClick).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the close button is clicked", () => {
    const props = createProps();
    render(<ConfirmModal {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking the backdrop", () => {
    const props = createProps();
    const { container } = render(<ConfirmModal {...props} />);

    fireEvent.click(container.firstElementChild!);

    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("does not close when clicking inside the modal", () => {
    const props = createProps();
    render(<ConfirmModal {...props} />);

    fireEvent.click(
      screen.getByRole("heading", { name: "Delete account" }),
    );

    expect(props.onClose).not.toHaveBeenCalled();
  });

  it("does not close from the backdrop while processing", () => {
    const props = createProps({ isProcessing: true });
    const { container } = render(<ConfirmModal {...props} />);

    fireEvent.click(container.firstElementChild!);

    expect(props.onClose).not.toHaveBeenCalled();
  });

  it("disables the close button while processing", () => {
    render(<ConfirmModal {...createProps({ isProcessing: true })} />);

    expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();
  });

  it("disables all action buttons while processing", () => {
    render(<ConfirmModal {...createProps({ isProcessing: true })} />);

    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
  });

  it("disables an action when its disabled property is true", () => {
    const props = createProps({
      actions: [
        {
          label: "Unavailable",
          onClick: vi.fn(),
          disabled: true,
        },
      ],
    });

    render(<ConfirmModal {...props} />);

    expect(
      screen.getByRole("button", { name: "Unavailable" }),
    ).toBeDisabled();
  });

  it("disables a loading action and displays its loading label", () => {
    const onClick = vi.fn();

    render(
      <ConfirmModal
        {...createProps({
          actions: [
            {
              label: "Save",
              loadingLabel: "Saving...",
              loading: true,
              onClick,
            },
          ],
        })}
      />,
    );

    const button = screen.getByRole("button", { name: "Saving..." });

    expect(button).toBeDisabled();

    fireEvent.click(button);

    expect(onClick).not.toHaveBeenCalled();
  });

  it("uses the original label when loadingLabel is omitted", () => {
    render(
      <ConfirmModal
        {...createProps({
          actions: [
            {
              label: "Save",
              loading: true,
              onClick: vi.fn(),
            },
          ],
        })}
      />,
    );

    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("uses the primary variant by default", () => {
    render(
      <ConfirmModal
        {...createProps({
          actions: [{ label: "Continue", onClick: vi.fn() }],
        })}
      />,
    );

    expect(screen.getByRole("button", { name: "Continue" })).toHaveClass(
      "bg-primary",
    );
  });

  it("applies the correct styles for each action variant", () => {
    render(<ConfirmModal {...createProps()} />);

    expect(screen.getByRole("button", { name: "Confirm" })).toHaveClass(
      "bg-red-500",
    );
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveClass(
      "border",
      "border-border",
    );
  });

  it("applies rounded corners by default", () => {
    const { container } = render(<ConfirmModal {...createProps()} />);

    expect(container.querySelector(".rounded-xl")).toBeInTheDocument();
  });

  it("removes rounded corners when rounded is false", () => {
    const { container } = render(
      <ConfirmModal {...createProps({ rounded: false })} />,
    );

    const modal = container.querySelector(".max-w-md");

    expect(modal).not.toHaveClass("rounded-xl");
  });

  it("renders all provided actions", () => {
    render(
      <ConfirmModal
        {...createProps({
          actions: [
            { label: "One", onClick: vi.fn() },
            { label: "Two", onClick: vi.fn() },
            { label: "Three", onClick: vi.fn() },
          ],
        })}
      />,
    );

    expect(screen.getByRole("button", { name: "One" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Two" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Three" }),
    ).toBeInTheDocument();
  });
});