import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { useCalendarSync } from "../../hooks/useCalendarSync";
import type { CalendarProvider } from "../../types";
import { CalendarSyncPanel } from "../CalendarSyncPanel";

type Calendar = ReturnType<typeof useCalendarSync>;

function calendario(provider: CalendarProvider, cambios: Partial<Calendar> = {}): Calendar {
  return {
    provider,
    state: { status: "idle" },
    connection: { provider, connected: false, account_email: null, needs_reconnect: false },
    available: true,
    loadingConnection: false,
    sync: vi.fn(),
    confirmTime: vi.fn(),
    cancelTime: vi.fn(),
    retry: vi.fn(),
    disconnect: vi.fn(),
    ...cambios,
  };
}

describe("CalendarSyncPanel", () => {
  it("sin hitos elegidos no deja sincronizar", () => {
    render(<CalendarSyncPanel calendars={[calendario("google")]} selectedCount={0} onSync={vi.fn()} />);

    expect(screen.getByRole("button", { name: /sincronizar con mi calendario/i })).toBeDisabled();
  });

  it("con dos calendarios, el que se elige en el menú es el que se sincroniza", async () => {
    const user = userEvent.setup();
    const outlook = calendario("outlook");
    const onSync = vi.fn();
    render(
      <CalendarSyncPanel calendars={[calendario("google"), outlook]} selectedCount={2} onSync={onSync} />,
    );

    await user.click(screen.getByRole("button", { name: /sincronizar con mi calendario \(2\)/i }));
    await user.click(screen.getByRole("menuitem", { name: /outlook calendar/i }));

    expect(onSync).toHaveBeenCalledWith(outlook);
  });

  it("si un calendario pide reconectar, el botón nombra a ese calendario", async () => {
    const user = userEvent.setup();
    const outlook = calendario("outlook", {
      state: {
        status: "error",
        message: "La sincronización no pudo completarse.",
        retryIds: ["m-1"],
        reconnect: true,
      },
    });
    render(<CalendarSyncPanel calendars={[calendario("google"), outlook]} selectedCount={1} onSync={vi.fn()} />);

    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent("La sincronización no pudo completarse.");
    await user.click(within(alerta).getByRole("button", { name: "Reconectar Outlook Calendar" }));

    expect(outlook.retry).toHaveBeenCalledTimes(1);
  });

  it("desconecta solo el calendario elegido", async () => {
    const user = userEvent.setup();
    const google = calendario("google", {
      connection: { provider: "google", connected: true, account_email: "u@gmail.com", needs_reconnect: false },
    });
    const outlook = calendario("outlook", {
      connection: { provider: "outlook", connected: true, account_email: "u@outlook.com", needs_reconnect: false },
    });
    render(<CalendarSyncPanel calendars={[google, outlook]} selectedCount={0} onSync={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Desconectar Outlook Calendar" }));

    expect(outlook.disconnect).toHaveBeenCalledTimes(1);
    expect(google.disconnect).not.toHaveBeenCalled();
  });

  it("si el acceso expiró lo dice para ese calendario", () => {
    render(
      <CalendarSyncPanel
        calendars={[
          calendario("google", {
            connection: { provider: "google", connected: false, account_email: null, needs_reconnect: true },
          }),
        ]}
        selectedCount={0}
        onSync={vi.fn()}
      />,
    );

    expect(screen.getByText(/google calendar: tu acceso expiró/i)).toBeInTheDocument();
  });
});
