import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationPanel } from "../NotificationPanel";
import type { NotificationItem } from "../../notificationTypes";
import type { Tender } from "@/features/matches/tenderTypes";

const getNotifications = vi.fn();
const markNotificationRead = vi.fn();
const markAllNotificationsRead = vi.fn();

vi.mock("../../services/notificationService", () => ({
  getNotifications: (...args: unknown[]) => getNotifications(...args),
  getUnreadCount: () => Promise.resolve({ count: 0 }),
  markNotificationRead: (...args: unknown[]) => markNotificationRead(...args),
  markAllNotificationsRead: () => markAllNotificationsRead(),
}));

function tender(overrides: Partial<Tender> = {}): Tender {
  return {
    id: "t1",
    code: "1057539-228-COT26",
    name: "Mantención de áreas verdes",
    description: null,
    status_id: 1,
    status_code: "publicada",
    published_at: "2026-08-01T12:00:00Z",
    closing_at: "2026-09-30T12:00:00Z",
    last_change_at: "2026-08-01T12:00:00Z",
    buyer_rut: "61.980.170-9",
    buyer_name: "Municipalidad de Providencia",
    buyer_unit: "Operaciones",
    region: "Región Metropolitana de Santiago",
    available_amount_clp: 5_000_000,
    created_at: "2026-08-01T12:00:00Z",
    updated_at: "2026-08-01T12:00:00Z",
    items: [],
    ...overrides,
  };
}

function aviso(overrides: Partial<NotificationItem> = {}): NotificationItem {
  return {
    id: "n1",
    tender_id: "t1",
    score_pct: 84,
    read_at: null,
    created_at: "2026-08-26T12:00:00Z",
    is_closed: false,
    tender: tender(),
    ...overrides,
  };
}

beforeEach(() => {
  getNotifications.mockResolvedValue([]);
  markNotificationRead.mockResolvedValue(aviso());
  markAllNotificationsRead.mockResolvedValue({ updated: 1 });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("NotificationPanel", () => {
  it("muestra un estado vacío cuando no hay alertas", async () => {
    render(<NotificationPanel />);

    expect(await screen.findByText(/Todavía no hay alertas/)).toBeInTheDocument();
  });

  it("lista la licitación con su compatibilidad y organismo", async () => {
    getNotifications.mockResolvedValue([aviso()]);

    render(<NotificationPanel />);

    expect(
      await screen.findByText("Mantención de áreas verdes"),
    ).toBeInTheDocument();
    expect(screen.getByText("84%")).toBeInTheDocument();
    expect(
      screen.getByText(/Municipalidad de Providencia/),
    ).toBeInTheDocument();
  });

  it("enlaza a la ficha de la licitación", async () => {
    getNotifications.mockResolvedValue([aviso()]);

    render(<NotificationPanel />);

    const enlace = await screen.findByRole("link", {
      name: /Mantención de áreas verdes/,
    });
    expect(enlace).toHaveAttribute("href", "/matches/t1");
  });

  it("avisa cuando la licitación ya cerró", async () => {
    // Criterio: una alerta antigua puede apuntar a una licitación vencida.
    getNotifications.mockResolvedValue([aviso({ is_closed: true })]);

    render(<NotificationPanel />);

    expect(await screen.findByText("Cerrada")).toBeInTheDocument();
  });

  it("marca el aviso como leído al abrirlo", async () => {
    getNotifications.mockResolvedValue([aviso()]);
    render(<NotificationPanel />);
    const enlace = await screen.findByRole("link", {
      name: /Mantención de áreas verdes/,
    });

    await userEvent.click(enlace);

    await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith("n1"));
  });

  it("permite marcar todas como leídas cuando hay alguna sin leer", async () => {
    getNotifications.mockResolvedValue([aviso()]);
    render(<NotificationPanel />);

    const boton = await screen.findByRole("button", {
      name: /Marcar todo como leído/,
    });
    await userEvent.click(boton);

    expect(markAllNotificationsRead).toHaveBeenCalled();
  });

  it("no ofrece marcar todo cuando ya está todo leído", async () => {
    getNotifications.mockResolvedValue([
      aviso({ read_at: "2026-08-26T13:00:00Z" }),
    ]);

    render(<NotificationPanel />);
    await screen.findByText("Mantención de áreas verdes");

    expect(
      screen.queryByRole("button", { name: /Marcar todo como leído/ }),
    ).not.toBeInTheDocument();
  });

  it("muestra un error con reintento si la carga falla", async () => {
    getNotifications.mockRejectedValue(new Error("boom"));

    render(<NotificationPanel />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Reintentar/ }),
    ).toBeInTheDocument();
  });
});
