import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationSettings } from "../NotificationSettings";
import type { NotificationPreferences } from "../../notificationTypes";

const getNotificationPreferences = vi.fn();
const updateNotificationPreferences = vi.fn();
const reactivateEmailDelivery = vi.fn();
const getDeliveries = vi.fn();

vi.mock("../../services/notificationService", () => ({
  getNotificationPreferences: () => getNotificationPreferences(),
  updateNotificationPreferences: (...args: unknown[]) =>
    updateNotificationPreferences(...args),
  reactivateEmailDelivery: () => reactivateEmailDelivery(),
  getDeliveries: () => getDeliveries(),
}));

function preferencias(
  overrides: Partial<NotificationPreferences> = {},
): NotificationPreferences {
  return {
    enabled: true,
    threshold_pct: 70,
    delivery_mode: "immediate",
    email_delivery_enabled: true,
    last_failure_reason: null,
    last_failure_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  getNotificationPreferences.mockResolvedValue(preferencias());
  updateNotificationPreferences.mockImplementation((cambio) =>
    Promise.resolve(preferencias(cambio as Partial<NotificationPreferences>)),
  );
  reactivateEmailDelivery.mockResolvedValue(preferencias());
  getDeliveries.mockResolvedValue([]);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("NotificationSettings", () => {
  it("muestra el umbral guardado", async () => {
    render(<NotificationSettings />);

    expect(await screen.findByText("70%")).toBeInTheDocument();
  });

  it("permite apagar las alertas", async () => {
    render(<NotificationSettings />);
    const interruptor = await screen.findByRole("switch");

    await userEvent.click(interruptor);

    await waitFor(() =>
      expect(updateNotificationPreferences).toHaveBeenCalledWith({
        enabled: false,
      }),
    );
  });

  it("ofrece los dos modos de entrega del criterio", async () => {
    render(<NotificationSettings />);

    expect(await screen.findByLabelText(/Aviso inmediato/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Resumen diario/)).toBeInTheDocument();
  });

  it("guarda el cambio a resumen diario", async () => {
    render(<NotificationSettings />);
    const opcion = await screen.findByLabelText(/Resumen diario/);

    await userEvent.click(opcion);

    await waitFor(() =>
      expect(updateNotificationPreferences).toHaveBeenCalledWith({
        delivery_mode: "daily_digest",
      }),
    );
  });

  it("avisa cuando el sistema desactivó el envío de correos", async () => {
    // Criterio: si el correo del usuario no existe, el sistema desactiva las
    // alertas y se lo muestra en su sección de notificaciones.
    getNotificationPreferences.mockResolvedValue(
      preferencias({
        email_delivery_enabled: false,
        last_failure_reason: "la dirección no existe",
        last_failure_at: "2026-08-26T12:00:00Z",
      }),
    );

    render(<NotificationSettings />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/la dirección no existe/)).toBeInTheDocument();
  });

  it("permite reactivar el envío tras corregir el correo", async () => {
    getNotificationPreferences.mockResolvedValue(
      preferencias({ email_delivery_enabled: false }),
    );
    render(<NotificationSettings />);
    const boton = await screen.findByRole("button", {
      name: /Reactivar envío de correos/,
    });

    await userEvent.click(boton);

    expect(reactivateEmailDelivery).toHaveBeenCalled();
  });

  it("no muestra la alerta de fallo cuando el correo funciona", async () => {
    render(<NotificationSettings />);
    await screen.findByText("70%");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("muestra un error con reintento si no puede cargar", async () => {
    getNotificationPreferences.mockRejectedValue(new Error("boom"));

    render(<NotificationSettings />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reintentar/ })).toBeInTheDocument();
  });
});
