import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useOnboardingStore } from "@/features/onboarding/store/useOnboardingStore";
import { Sidebar } from "../Sidebar";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
  usePathname: () => "/",
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "u-1", full_name: "Ana Pérez", email: "ana@empresa.cl" },
    logout: vi.fn(),
  }),
}));

vi.mock("@/features/company-profile/components/CompanyProvider", () => ({
  useCompany: () => ({
    company: {
      status: "with-company",
      supplier: { id: "sup-1", name: "Empresa Demo" },
    },
  }),
}));

vi.mock("@/features/workspaces/WorkspaceContext", () => ({
  useWorkspace: () => ({
    activeWorkspace: null,
    invitations: [],
    workspaces: [],
    recentWorkspaces: [],
  }),
}));

vi.mock("@/features/workspaces/components/WorkspaceSelector", () => ({
  WorkspaceSelector: () => <div data-testid="workspace-selector" />,
}));

vi.mock("@/features/notifications/hooks/useNotifications", () => ({
  useUnreadCount: () => 0,
}));

describe("Sidebar - Onboarding & Help Center integration", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useOnboardingStore.setState({
      tours: { home: true, detail: false, draft: false },
      activeTour: null,
      currentTourStep: 0,
      isHelpCenterOpen: false,
      _hasHydrated: true,
    });
  });

  it("asigna data-tour='sidebar-search' al enlace de Buscar", () => {
    render(<Sidebar />);

    const searchLink = screen.getByRole("link", { name: /Buscar/i });
    expect(searchLink).toHaveAttribute("data-tour", "sidebar-search");
  });

  it("asigna los atributos data-tour para matches, seguimiento, administración y ayuda", () => {
    const { container } = render(<Sidebar />);

    const matchesLink = screen.getByRole("link", { name: /Matches/i });
    expect(matchesLink).toHaveAttribute("data-tour", "sidebar-matches");

    const seguimientoSection = container.querySelector('[data-tour="sidebar-seguimiento"]');
    expect(seguimientoSection).toBeInTheDocument();

    const administracionSection = container.querySelector('[data-tour="sidebar-administracion"]');
    expect(administracionSection).toBeInTheDocument();

    const helpButton = screen.getByRole("button", { name: /Ayuda/i });
    expect(helpButton).toHaveAttribute("data-tour", "help-center-trigger");
  });

  it("abre el Centro de Ayuda al hacer clic en el botón 'Ayuda'", () => {
    render(<Sidebar />);

    const helpButton = screen.getByRole("button", { name: /Ayuda/i });
    fireEvent.click(helpButton);

    expect(useOnboardingStore.getState().isHelpCenterOpen).toBe(true);
  });
});
