import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "../Sidebar";

let pathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({ user: { full_name: "Ana" }, logout: vi.fn() }),
}));

vi.mock("@/features/company-profile/components/CompanyProvider", () => ({
  useCompany: () => ({ company: { status: "without-company" } }),
}));

vi.mock("@/features/notifications/hooks/useNotifications", () => ({
  useUnreadCount: () => 0,
}));

vi.mock("@/features/workspaces/WorkspaceContext", () => ({
  useWorkspace: () => ({ activeWorkspace: null, invitations: [] }),
}));

vi.mock("@/features/workspaces/components/WorkspaceSelector", () => ({
  WorkspaceSelector: () => null,
}));

describe("Sidebar", () => {
  it("ofrece el mapa de licitaciones en el menú (HU-22)", () => {
    render(<Sidebar />);

    expect(screen.getByRole("link", { name: /mapa de licitaciones/i })).toHaveAttribute(
      "href",
      "/mapa",
    );
  });

  it("el ítem del mapa dibuja su ícono", () => {
    // `Icon` devuelve null si el nombre no está en su registro, así que un ícono
    // sin registrar desaparece sin romper nada: solo deja un aviso en consola.
    render(<Sidebar />);

    const mapa = screen.getByRole("link", { name: /mapa de licitaciones/i });
    expect(mapa.querySelector("svg")).not.toBeNull();
  });

  it("marca el mapa como la página actual en /mapa", () => {
    pathname = "/mapa";

    render(<Sidebar />);

    expect(screen.getByRole("link", { name: /mapa de licitaciones/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});
