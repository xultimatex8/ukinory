
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import RegisterScreen from "./index";
import { register } from "../../services/auth";
import { claimGuest } from "../../services/user";
import { useLegalDocuments } from "../../hooks/useLegalDocuments";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  location: {
    pathname: "/register",
    state: undefined as { from?: { pathname: string } } | undefined,
  },
  reloadDocuments: vi.fn<() => Promise<void>>(),
}));

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();

  return {
    ...actual,
    useNavigate: () => mocks.navigate,
    useLocation: () => mocks.location,
  };
});

vi.mock("../../services/auth", () => ({
  register: vi.fn(),
}));

vi.mock("../../services/user", () => ({
  claimGuest: vi.fn(),
}));

vi.mock("../../hooks/useLegalDocuments", () => ({
  useLegalDocuments: vi.fn(),
}));

vi.mock("../../components/LogoHeader", () => ({
  default: ({
    title,
    description,
  }: {
    title: string;
    description: string;
  }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  ),
}));

vi.mock("../../components/legal/LegalLinks", () => ({
  default: ({
    documents,
  }: {
    documents: Array<{ id: number | string; title: string }> | null;
  }) => (
    <span>
      {documents?.map((document) => (
        <span key={document.id}>{document.title}</span>
      ))}
    </span>
  ),
}));

const legalDocuments = [
  {
    id: 1,
    title: "Terms and Conditions",
    type: "terms",
    version: "1.0",
    content: "Terms and conditions content",
    effective_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    title: "Privacy Policy",
    type: "privacy",
    version: "1.0",
    content: "Privacy policy content",
    effective_at: "2026-01-01T00:00:00Z",
  },
];

const validForm = {
  username: "cinema_user",
  email: "cinema@example.com",
  password: "StrongPassword123!",
  confirmPassword: "StrongPassword123!",
};

function renderScreen(pathname = "/register") {
  mocks.location.pathname = pathname;
  mocks.location.state = undefined;

  return render(
    <MemoryRouter>
      <RegisterScreen />
    </MemoryRouter>,
  );
}

function fillValidForm() {
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: validForm.username },
  });

  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: validForm.email },
  });

  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: validForm.password },
  });

  fireEvent.change(screen.getByLabelText("Confirm password"), {
    target: { value: validForm.confirmPassword },
  });

  fireEvent.click(screen.getByRole("checkbox", { name: /i accept/i }));
}

describe("RegisterScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    mocks.location.pathname = "/register";
    mocks.location.state = undefined;

    mocks.reloadDocuments.mockResolvedValue(undefined);

    vi.mocked(useLegalDocuments).mockReturnValue({
      documents: legalDocuments,
      isLoading: false,
      error: null,
      reload: mocks.reloadDocuments,
    } as ReturnType<typeof useLegalDocuments>);

    vi.mocked(register).mockResolvedValue({
      access: "access-token",
      refresh: "refresh-token",
    } as Awaited<ReturnType<typeof register>>);

    vi.mocked(claimGuest).mockResolvedValue({
      access: "claim-access-token",
      refresh: "claim-refresh-token",
    } as Awaited<ReturnType<typeof claimGuest>>);
  });

  it("renders the registration form and legal documents", () => {
    renderScreen();

    expect(
      screen.getByRole("heading", { name: "Create your account" }),
    ).toBeInTheDocument();

    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();

    expect(screen.getByRole("checkbox")).not.toBeChecked();

    expect(screen.getByText("Terms and Conditions")).toBeInTheDocument();
    expect(screen.getByText("Privacy Policy")).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Create account" }),
    ).toBeEnabled();

    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("shows the claim-account content on the claim route", () => {
    renderScreen("/register/claim");

    expect(
      screen.getByRole("heading", { name: "Claim your account" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Claim account" }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("link", { name: "Sign in" }),
    ).not.toBeInTheDocument();
  });

  it("toggles password visibility", () => {
    renderScreen();

    const password = screen.getByLabelText("Password");

    expect(password).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "Show password" }));

    expect(password).toHaveAttribute("type", "text");

    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));

    expect(password).toHaveAttribute("type", "password");
  });

  it("toggles confirmation-password visibility independently", () => {
    renderScreen();

    const password = screen.getByLabelText("Password");
    const confirmation = screen.getByLabelText("Confirm password");

    fireEvent.click(
      screen.getByRole("button", { name: "Show confirm password" }),
    );

    expect(confirmation).toHaveAttribute("type", "text");
    expect(password).toHaveAttribute("type", "password");

    fireEvent.click(
      screen.getByRole("button", { name: "Hide confirm password" }),
    );

    expect(confirmation).toHaveAttribute("type", "password");
  });

  it("navigates back when Back is clicked", () => {
    renderScreen();

    fireEvent.click(screen.getByRole("button", { name: /back/i }));

    expect(mocks.navigate).toHaveBeenCalledWith(-1);
  });

  it("registers a user and stores the returned tokens", async () => {
    renderScreen();

    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(register).toHaveBeenCalledWith({
        username: validForm.username,
        email: validForm.email,
        password: validForm.password,
        accepted_documents: [1, 2],
      });
    });

    await waitFor(() => {
      expect(localStorage.getItem("access_token")).toBe("access-token");
      expect(localStorage.getItem("refresh_token")).toBe("refresh-token");

      expect(mocks.navigate).toHaveBeenCalledWith(
        { pathname: "/" },
        { replace: true },
      );
    });

    expect(claimGuest).not.toHaveBeenCalled();
  });

  it("claims a guest account on the claim route", async () => {
    renderScreen("/register/claim");

    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Claim account" }));

    await waitFor(() => {
      expect(claimGuest).toHaveBeenCalledWith({
        username: validForm.username,
        email: validForm.email,
        password: validForm.password,
        accepted_documents: [1, 2],
      });
    });

    await waitFor(() => {
      expect(localStorage.getItem("access_token")).toBe(
        "claim-access-token",
      );
      expect(localStorage.getItem("refresh_token")).toBe(
        "claim-refresh-token",
      );

      expect(mocks.navigate).toHaveBeenCalledWith(
        { pathname: "/" },
        { replace: true },
      );
    });

    expect(register).not.toHaveBeenCalled();
  });

  it("uses the destination supplied in location state after registration", async () => {
    mocks.location.state = {
      from: { pathname: "/watchlist" },
    };

    render(
      <MemoryRouter>
        <RegisterScreen />
      </MemoryRouter>,
    );

    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(mocks.navigate).toHaveBeenCalledWith(
        { pathname: "/watchlist" },
        { replace: true },
      );
    });
  });

  it("does not submit when legal documents have not loaded", () => {
    vi.mocked(useLegalDocuments).mockReturnValue({
      documents: null,
      isLoading: true,
      error: null,
      reload: mocks.reloadDocuments,
    } as ReturnType<typeof useLegalDocuments>);

    renderScreen();

    expect(
      screen.getByRole("button", { name: "Create account" }),
    ).toBeDisabled();

    expect(register).not.toHaveBeenCalled();
  });

  it("shows the legal-document loading error and retries loading", () => {
    vi.mocked(useLegalDocuments).mockReturnValue({
      documents: null,
      isLoading: false,
      error: "Unable to load legal documents.",
      reload: mocks.reloadDocuments,
    } as ReturnType<typeof useLegalDocuments>);

    renderScreen();

    expect(
      screen.getByText("Unable to load legal documents."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(mocks.reloadDocuments).toHaveBeenCalledOnce();
  });

  it("shows a root error when submitting without legal documents", async () => {
    vi.mocked(useLegalDocuments).mockReturnValue({
      documents: null,
      isLoading: false,
      error: null,
      reload: mocks.reloadDocuments,
    } as ReturnType<typeof useLegalDocuments>);

    renderScreen();

    // Complete the form first so react-hook-form can call handleSubmitForm.
    // The submit button is disabled when documents are null, so submit the form
    // directly to exercise the missing-documents guard.
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: validForm.username },
    });

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: validForm.email },
    });

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: validForm.password },
    });

    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: validForm.confirmPassword },
    });

    fireEvent.click(screen.getByRole("checkbox", { name: /i accept/i }));

    const form = document.querySelector("form");

    expect(form).not.toBeNull();

    if (form) {
      fireEvent.submit(form);
    }

    expect(
      await screen.findByText(
        "Unable to load the Terms and Conditions. Please try again.",
      ),
    ).toBeInTheDocument();

    expect(register).not.toHaveBeenCalled();
  });

  it("displays a username error returned by the backend", async () => {
    vi.mocked(register).mockRejectedValue({
      username: ["This username is already taken."],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("This username is already taken."),
    ).toBeInTheDocument();
  });

  it("displays an email error returned by the backend", async () => {
    vi.mocked(register).mockRejectedValue({
      email: ["This email is already registered."],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("This email is already registered."),
    ).toBeInTheDocument();
  });

  it("displays a password error returned by the backend", async () => {
    vi.mocked(register).mockRejectedValue({
      password: ["This password is not allowed."],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("This password is not allowed."),
    ).toBeInTheDocument();
  });

  it("displays the first message when a backend field error is an array", async () => {
    vi.mocked(register).mockRejectedValue({
      email: ["First error", "Second error"],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("First error")).toBeInTheDocument();
    expect(screen.queryByText("Second error")).not.toBeInTheDocument();
  });

  it("displays the backend detail message", async () => {
    vi.mocked(register).mockRejectedValue({
      detail: "Registration is temporarily unavailable.",
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("Registration is temporarily unavailable."),
    ).toBeInTheDocument();
  });

  it("displays the first detail message when detail is an array", async () => {
    vi.mocked(register).mockRejectedValue({
      detail: ["First detail", "Second detail"],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("First detail")).toBeInTheDocument();
  });

  it("shows the generic error when registration rejects with a primitive", async () => {
    vi.mocked(register).mockRejectedValue("Network failure");

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("Unable to create your account."),
    ).toBeInTheDocument();
  });

  it("shows the generic claim error when claiming rejects with a primitive", async () => {
    vi.mocked(claimGuest).mockRejectedValue("Network failure");

    renderScreen("/register/claim");
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Claim account" }));

    expect(
      await screen.findByText("Unable to claim your account."),
    ).toBeInTheDocument();
  });

  it("reloads legal documents and resets acceptance when they changed", async () => {
    vi.mocked(register).mockRejectedValue({
      accepted_documents: ["Documents have changed."],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText(
        "The Terms and Conditions or Privacy Policy have changed. Please review them and accept again.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("checkbox", { name: /i accept/i }),
    ).not.toBeChecked();

    expect(mocks.reloadDocuments).toHaveBeenCalledOnce();
  });

  it("clears a server username error when the username changes", async () => {
    vi.mocked(register).mockRejectedValue({
      username: ["This username is already taken."],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("This username is already taken."),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: `${validForm.username}_new` },
    });

    await waitFor(() => {
      expect(
        screen.queryByText("This username is already taken."),
      ).not.toBeInTheDocument();
    });
  });

  it("clears a server email error when the email changes", async () => {
    vi.mocked(register).mockRejectedValue({
      email: ["This email is already registered."],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("This email is already registered."),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "cinema.new@example.com" },
    });

    await waitFor(() => {
      expect(
        screen.queryByText("This email is already registered."),
      ).not.toBeInTheDocument();
    });
  });

  it("clears a server password error when the password changes", async () => {
    vi.mocked(register).mockRejectedValue({
      password: ["This password is not allowed."],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText("This password is not allowed."),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: `${validForm.password}X` },
    });

    await waitFor(() => {
      expect(
        screen.queryByText("This password is not allowed."),
      ).not.toBeInTheDocument();
    });
  });

  it("clears a terms server error when acceptance changes", async () => {
    vi.mocked(register).mockRejectedValue({
      accepted_documents: ["Changed"],
    });

    renderScreen();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText(
        "The Terms and Conditions or Privacy Policy have changed. Please review them and accept again.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /i accept/i }));

    await waitFor(() => {
      expect(
        screen.queryByText(
          "The Terms and Conditions or Privacy Policy have changed. Please review them and accept again.",
        ),
      ).not.toBeInTheDocument();
    });
  });
});