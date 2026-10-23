import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import DeleteAccountModal from "./DeleteAccountModal";

describe("DeleteAccountModal", () => {
  const createProps = (
    overrides: Partial<React.ComponentProps<typeof DeleteAccountModal>> = {},
  ) => ({
    isDeleting: false,
    isGuest: false,
    error: null,
    onClose: vi.fn(),
    onConfirm: vi.fn(),
    ...overrides,
  });

  it("renders the title, description and account deletion actions", () => {
    render(<DeleteAccountModal {...createProps()} />);

    expect(
      screen.getByRole("heading", { name: "Delete account?" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/This action is permanent/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cancel" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete account" }),
    ).toBeInTheDocument();
  });

  it("shows the password field for non-guest users", () => {
    render(<DeleteAccountModal {...createProps({ isGuest: false })} />);

    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Enter your password"),
    ).toHaveAttribute("type", "password");
  });

  it("does not show the password field for guest users", () => {
    render(<DeleteAccountModal {...createProps({ isGuest: true })} />);

    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Show password" }),
    ).not.toBeInTheDocument();
  });

  it("disables confirmation when a non-guest password is empty", () => {
    render(<DeleteAccountModal {...createProps()} />);

    expect(
      screen.getByRole("button", { name: "Delete account" }),
    ).toBeDisabled();
  });

  it("enables confirmation when a non-guest enters a password", () => {
    render(<DeleteAccountModal {...createProps()} />);

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret123" },
    });

    expect(
      screen.getByRole("button", { name: "Delete account" }),
    ).toBeEnabled();
  });

  it("passes the entered password to onConfirm", () => {
    const props = createProps();
    render(<DeleteAccountModal {...props} />);

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret123" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Delete account" }),
    );

    expect(props.onConfirm).toHaveBeenCalledOnce();
    expect(props.onConfirm).toHaveBeenCalledWith("secret123");
  });

  it("calls onConfirm without arguments for a guest user", () => {
    const props = createProps({ isGuest: true });
    render(<DeleteAccountModal {...props} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Delete account" }),
    );

    expect(props.onConfirm).toHaveBeenCalledOnce();
    expect(props.onConfirm).toHaveBeenCalledWith();
  });

  it("toggles password visibility", () => {
    render(<DeleteAccountModal {...createProps()} />);

    const passwordInput = screen.getByLabelText("Password");

    expect(passwordInput).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "Show password" }));

    expect(passwordInput).toHaveAttribute("type", "text");
    expect(
      screen.getByRole("button", { name: "Hide password" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));

    expect(passwordInput).toHaveAttribute("type", "password");
    expect(
      screen.getByRole("button", { name: "Show password" }),
    ).toBeInTheDocument();
  });

  it("renders an error when provided", () => {
    render(
      <DeleteAccountModal
        {...createProps({ error: "Incorrect password" })}
      />,
    );

    expect(screen.getByText("Incorrect password")).toBeInTheDocument();
  });

  it("does not render an error when error is null", () => {
    render(<DeleteAccountModal {...createProps({ error: null })} />);

    expect(screen.queryByText("Incorrect password")).not.toBeInTheDocument();
  });

  it("shows the deleting label while deletion is in progress", () => {
    render(<DeleteAccountModal {...createProps({ isDeleting: true })} />);

    expect(
      screen.getByRole("button", { name: "Deleting account..." }),
    ).toBeInTheDocument();
  });

  it("disables the confirmation button while deleting", () => {
    render(
      <DeleteAccountModal
        {...createProps({ isDeleting: true, isGuest: true })}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Deleting account..." }),
    ).toBeDisabled();
  });

  it("disables the password input and visibility toggle while deleting", () => {
    render(<DeleteAccountModal {...createProps({ isDeleting: true })} />);

    expect(screen.getByLabelText("Password")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Show password" }),
    ).toBeDisabled();
  });

  it("disables the close and cancel buttons while deleting", () => {
    render(<DeleteAccountModal {...createProps({ isDeleting: true })} />);

    expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("calls onClose when the close button is clicked", () => {
    const props = createProps();
    render(<DeleteAccountModal {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(props.onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when the cancel button is clicked", () => {
    const props = createProps();
    render(<DeleteAccountModal {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(props.onClose).toHaveBeenCalledOnce();
  });

  it("closes when the backdrop is clicked", () => {
    const props = createProps();
    const { container } = render(<DeleteAccountModal {...props} />);

    fireEvent.click(container.firstElementChild!);

    expect(props.onClose).toHaveBeenCalledOnce();
  });

  it("does not close when the modal content is clicked", () => {
    const props = createProps();
    render(<DeleteAccountModal {...props} />);

    fireEvent.click(
      screen.getByRole("heading", { name: "Delete account?" }),
    );

    expect(props.onClose).not.toHaveBeenCalled();
  });

  it("does not close when the backdrop is clicked during deletion", () => {
    const props = createProps({ isDeleting: true });
    const { container } = render(<DeleteAccountModal {...props} />);

    fireEvent.click(container.firstElementChild!);

    expect(props.onClose).not.toHaveBeenCalled();
  });

  it("does not call onConfirm when a non-guest password is empty", () => {
    const props = createProps();
    render(<DeleteAccountModal {...props} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Delete account" }),
    );

    expect(props.onConfirm).not.toHaveBeenCalled();
  });

  it("uses current-password autocomplete for the password field", () => {
    render(<DeleteAccountModal {...createProps()} />);

    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "autocomplete",
      "current-password",
    );
  });
});