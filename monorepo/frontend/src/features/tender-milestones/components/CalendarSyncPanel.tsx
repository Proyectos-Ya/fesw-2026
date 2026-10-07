"use client";

import { useState } from "react";

import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";

import type { useCalendarSync } from "../hooks/useCalendarSync";
import { CALENDAR_ACCOUNT_LABELS, CALENDAR_PROVIDER_LABELS } from "../types";
import { SyncErrorAlert } from "./SyncErrorAlert";

type Calendar = ReturnType<typeof useCalendarSync>;

interface CalendarSyncPanelProps {
  /** Los calendarios configurados en el servidor; con uno no hay menú. */
  calendars: Calendar[];
  selectedCount: number;
  onSync: (calendar: Calendar) => void;
}

function successMessage(count: number, label: string): string {
  return count === 1 ? `1 hito sincronizado con ${label}.` : `${count} hitos sincronizados con ${label}.`;
}

function connectionText(calendar: Calendar): string {
  const label = CALENDAR_PROVIDER_LABELS[calendar.provider];
  const { connection } = calendar;
  if (connection?.connected) {
    return `${label}: conectado como ${connection.account_email ?? CALENDAR_ACCOUNT_LABELS[calendar.provider].account}`;
  }
  if (connection?.needs_reconnect) {
    return `${label}: tu acceso expiró; al sincronizar te pediremos autorizarlo de nuevo.`;
  }
  return `${label}: sin conectar. Al sincronizar te pediremos autorizar el acceso.`;
}

/**
 * Botón "Sincronizar con mi calendario" (HU-16, criterio 2). Con un solo
 * calendario configurado sincroniza directo; con Google y Outlook abre un menú
 * para elegir. Debajo, el estado y los mensajes de cada calendario.
 */
export function CalendarSyncPanel({ calendars, selectedCount, onSync }: CalendarSyncPanelProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const busy = calendars.some((c) => c.state.status === "syncing" || c.state.status === "redirecting");
  const withMenu = calendars.length > 1;
  const count = selectedCount > 0 ? ` (${selectedCount})` : "";

  const choose = (calendar: Calendar) => {
    setMenuOpen(false);
    onSync(calendar);
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-inset px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
        <ul className="space-y-1 text-xs text-text-muted">
          {calendars.map((calendar) => (
            <li key={calendar.provider} className="flex flex-wrap items-center gap-1">
              <span>{connectionText(calendar)}</span>
              {calendar.connection?.connected && (
                <>
                  <span aria-hidden="true">·</span>
                  <button
                    type="button"
                    onClick={() => void calendar.disconnect()}
                    aria-label={`Desconectar ${CALENDAR_PROVIDER_LABELS[calendar.provider]}`}
                    className="font-semibold text-primary hover:underline"
                  >
                    Desconectar
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>

        <div className="relative shrink-0">
          <Button
            onClick={() => (withMenu ? setMenuOpen((open) => !open) : choose(calendars[0]))}
            disabled={selectedCount === 0 || busy}
            isLoading={calendars.some((c) => c.state.status === "syncing")}
            aria-haspopup={withMenu ? "menu" : undefined}
            aria-expanded={withMenu ? menuOpen : undefined}
          >
            <Icon name="calendar-plus" size={14} />
            Sincronizar con mi calendario{count}
          </Button>

          {withMenu && menuOpen && (
            <>
              {/* Captura el clic fuera del menú para cerrarlo */}
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
              <div
                role="menu"
                className="absolute right-0 top-full z-20 mt-2 w-72 rounded-lg border border-border-subtle bg-white p-2 shadow-premium"
              >
                {calendars.map((calendar) => (
                  <button
                    key={calendar.provider}
                    type="button"
                    role="menuitem"
                    onClick={() => choose(calendar)}
                    className="flex w-full flex-col items-start rounded-md px-3 py-2 text-left transition-colors hover:bg-surface-inset"
                  >
                    <span className="text-sm font-semibold text-text-strong">
                      {CALENDAR_PROVIDER_LABELS[calendar.provider]}
                    </span>
                    <span className="text-xs text-text-subtle">
                      {calendar.connection?.connected
                        ? `Conectado como ${calendar.connection.account_email ?? CALENDAR_ACCOUNT_LABELS[calendar.provider].account}`
                        : "Sin conectar"}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {calendars.map((calendar) => (
        <CalendarStatus key={calendar.provider} calendar={calendar} />
      ))}
    </div>
  );
}

/** Lo que pasa con la sincronización de un calendario: en curso, éxito o error. */
function CalendarStatus({ calendar }: { calendar: Calendar }) {
  const { state, provider } = calendar;
  const label = CALENDAR_PROVIDER_LABELS[provider];
  const { vendor } = CALENDAR_ACCOUNT_LABELS[provider];

  if (state.status === "syncing") {
    return (
      <p role="status" className="text-xs text-text-muted">
        Sincronizando con {label}…
      </p>
    );
  }
  if (state.status === "redirecting") {
    return (
      <p role="status" className="text-xs text-text-muted">
        Te estamos llevando a {vendor} para autorizar el acceso…
      </p>
    );
  }
  if (state.status === "success") {
    return (
      <p role="status" className="text-xs font-semibold text-success">
        {successMessage(state.count, label)}
      </p>
    );
  }
  if (state.status === "error") {
    return (
      <SyncErrorAlert
        message={state.message}
        reconnect={state.reconnect}
        providerLabel={label}
        onRetry={() => void calendar.retry()}
      />
    );
  }
  return null;
}
