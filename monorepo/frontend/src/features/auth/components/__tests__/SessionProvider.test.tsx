import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionProvider, useSession } from "../SessionProvider";
import { ApiError } from "@/features/shared/api/client";
import type { UserPublic } from "../../authSchema";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
}));

const getMeMock = vi.fn();
const logoutMock = vi.fn();

vi.mock("../../services/authService", () => ({
  getMe: () => getMeMock() as Promise<UserPublic>,
  logout: () => logoutMock() as Promise<void>,
}));

const USER: UserPublic = {
  id: "user-1",
  email: "ana@example.com",
  full_name: "Ana Pérez",
  phone: null,
  active: true,
  email_verified: false,
  created_at: "2026-01-01T00:00:00Z",
};

function ShowUser() {
  const { user, isLoading } = useSession();
  if (isLoading) return <span>cargando</span>;
  return <span>{user?.full_name ?? "sin usuario"}</span>;
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("SessionProvider", () => {
  it("expone el usuario devuelto por GET /auth/me", async () => {
    getMeMock.mockResolvedValue(USER);

    render(
      <SessionProvider>
        <ShowUser />
      </SessionProvider>,
    );

    expect(await screen.findByText("Ana Pérez")).toBeInTheDocument();
  });

  it("redirige a /login cuando la sesión es inválida (401)", async () => {
    getMeMock.mockRejectedValue(new ApiError(401, "No autenticado"));

    render(
      <SessionProvider>
        <ShowUser />
      </SessionProvider>,
    );

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("useSession lanza error si se usa fuera del provider", () => {
    expect(() => render(<ShowUser />)).toThrow(
      "useSession debe usarse dentro de <SessionProvider>",
    );
  });
});
