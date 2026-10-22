
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import LoginScreen from "./index";
import { login } from "../../services/auth";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  location: {
    pathname: "/login",
    state: undefined as { from?: { pathname: string } } | undefined,
  },
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
  login: vi.fn(),
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

const validCredentials = {
  email: "cinema@example.com",
  password: "StrongPassword123!",
};

function renderScreen() {
  mocks.location.pathname = "/login";
  mocks.location.state = undefined;

  return render(
    <MemoryRouter>
      <LoginScreen />
    </MemoryRouter>,
  );
}

function fillValidForm() {
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: validCredentials.email },
  });

  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: validCredentials.password },
  });
}

function submitForm() {
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("LoginScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    mocks.location.pathname = "/login";
    mocks.location.state = undefined;

    vi.mocked(login).mockResolvedValue({
      access: "access-token",
      refresh: "refresh-token",
    } as Awaited<ReturnType<typeof login>>);
  });

  it("renders the login form", () => {
    renderScreen();

    expect(
      screen.getByRole("heading", { name: "Welcome back" }),
    ).toBeInTheDocument();

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Sign in" }),
    ).toBeEnabled();

    expect(
      screen.getByRole("link", { name: "Create one" }),
    ).toHaveAttribute("href", "/register");
  });

  it("shows required-field errors when submitting an empty form", async () => {
    renderScreen();

    submitForm();

    expect(await screen.findByText("Email is required.")).toBeInTheDocument();
    expect(
      await screen.findByText("Password is required."),
    ).toBeInTheDocument();

    expect(login).not.toHaveBeenCalled();
  });

  it("shows an email validation error for an invalid email", async () => {
    renderScreen();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "not-an-email" },
    });

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: validCredentials.password },
    });

    submitForm();

    expect(
      await screen.findByText("Enter a valid email address."),
    ).toBeInTheDocument();

    expect(login).not.toHaveBeenCalled();
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

  it("navigates back when Back is clicked", () => {
    renderScreen();

    fireEvent.click(screen.getByRole("button", { name: /back/i }));

    expect(mocks.navigate).toHaveBeenCalledWith(-1);
  });

  it("logs in and stores the returned tokens", async () => {
    renderScreen();

    fillValidForm();
    submitForm();

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith(validCredentials);
    });

    await waitFor(() => {
      expect(localStorage.getItem("access_token")).toBe("access-token");
      expect(localStorage.getItem("refresh_token")).toBe("refresh-token");

      expect(mocks.navigate).toHaveBeenCalledWith(
        { pathname: "/" },
        { replace: true },
      );
    });
  });

  it("uses the destination supplied in location state after login", async () => {
    mocks.location.state = {
      from: { pathname: "/watchlist" },
    };

    render(
      <MemoryRouter>
        <LoginScreen />
      </MemoryRouter>,
    );

    fillValidForm();
    submitForm();

    await waitFor(() => {
      expect(mocks.navigate).toHaveBeenCalledWith(
        { pathname: "/watchlist" },
        { replace: true },
      );
    });
  });

  it("displays an email error returned by the backend", async () => {
    vi.mocked(login).mockRejectedValue({
      email: ["This email is not registered."],
    });

    renderScreen();

    fillValidForm();
    submitForm();

    expect(
      await screen.findByText("This email is not registered."),
    ).toBeInTheDocument();

    expect(localStorage.getItem("access_token")).toBeNull();
  });

  it("displays a password error returned by the backend", async () => {
    vi.mocked(login).mockRejectedValue({
      password: ["Incorrect password."],
    });

    renderScreen();

    fillValidForm();
    submitForm();

    expect(
      await screen.findByText("Incorrect password."),
    ).toBeInTheDocument();

    expect(localStorage.getItem("access_token")).toBeNull();
  });

  it("clears the backend email error when the email changes", async () => {
    vi.mocked(login).mockRejectedValue({
      email: ["This email is not registered."],
    });

    renderScreen();

    fillValidForm();
    submitForm();

    expect(
      await screen.findByText("This email is not registered."),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@example.com" },
    });

    await waitFor(() => {
      expect(
        screen.queryByText("This email is not registered."),
      ).not.toBeInTheDocument();
    });
  });

  it("clears the backend password error when the password changes", async () => {
    vi.mocked(login).mockRejectedValue({
      password: ["Incorrect password."],
    });

    renderScreen();

    fillValidForm();
    submitForm();

    expect(
      await screen.findByText("Incorrect password."),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "AnotherStrongPassword123!" },
    });

    await waitFor(() => {
      expect(
        screen.queryByText("Incorrect password."),
      ).not.toBeInTheDocument();
    });
  });

  it("displays the backend detail message with a final period", async () => {
    vi.mocked(login).mockRejectedValue({
      detail: "Invalid credentials",
    });

    renderScreen();

    fillValidForm();
    submitForm();

    expect(
      await screen.findByText("Invalid credentials."),
    ).toBeInTheDocument();
  });

  it("shows the generic error when login rejects with a primitive", async () => {
    vi.mocked(login).mockRejectedValue("Network failure");

    renderScreen();

    fillValidForm();
    submitForm();

    expect(
      await screen.findByText("Unable to sign in."),
    ).toBeInTheDocument();
  });

  it("disables the submit button while login is pending", async () => {
    let resolveLogin!: (
      value: Awaited<ReturnType<typeof login>>,
    ) => void;

    vi.mocked(login).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLogin = resolve;
        }),
    );

    renderScreen();

    fillValidForm();
    submitForm();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Signing in..." }),
      ).toBeDisabled();
    });

    resolveLogin({
      access: "access-token",
      refresh: "refresh-token",
    } as Awaited<ReturnType<typeof login>>);
  });
});