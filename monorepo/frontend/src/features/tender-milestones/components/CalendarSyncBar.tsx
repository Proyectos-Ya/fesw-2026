"use client";

import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";

import type { useCalendarSync } from "../hooks/useCalendarSync";
import { CALENDAR_ACCOUNT_LABELS, CALENDAR_PROVIDER_LABELS } from "../types";
import { SyncErrorAlert } from "./SyncErrorAlert";

interface CalendarSyncBarProps {
  calendar: ReturnType<typeof useCalendarSync>;
  selectedCount: number;
  onSync: () => void;
}

function successMessage(count: number, label: string): string {
  return count === 1 ? `1 hito sincronizado con ${label}.` : `${count} hitos sincronizados con ${label}.`;
}

export function CalendarSyncBar({ calendar, selectedCount, onSync }: CalendarSyncBarProps) {
  const { state, connection, provider } = calendar;
  const label = CALENDAR_PROVIDER_LABELS[provider];
  const { vendor, account } = CALENDAR_ACCOUNT_LABELS[provider];
  const busy = state.status === "syncing" || state.status === "redirecting";

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-inset px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-xs text-text-muted">
          {connection?.connected ? (
            <span className="inline-flex flex-wrap items-center gap-1">
              <span>Conectado como {connection.account_email ?? account}</span>
              <span aria-hidden="true">·</span>
              <button
                type="button"
                onClick={() => void calendar.disconnect()}
                className="font-semibold text-primary hover:underline"
              >
                Desconectar
              </button>
            </span>
          ) : connection?.needs_reconnect ? (
            `Tu acceso a ${label} expiró: al sincronizar te pediremos autorizarlo de nuevo.`
          ) : (
            `Elige los hitos y te pediremos autorizar el acceso a tu ${label}.`
          )}
        </div>
        <Button
          onClick={onSync}
          disabled={selectedCount === 0 || busy}
          isLoading={state.status === "syncing"}
          className="shrink-0"
        >
          <Icon name="calendar-plus" size={14} />
          Sincronizar con {label}
          {selectedCount > 0 ? ` (${selectedCount})` : ""}
        </Button>
      </div>

      {state.status === "syncing" && (
        <p role="status" className="text-xs text-text-muted">
          Sincronizando con {label}…
        </p>
      )}
      {state.status === "redirecting" && (
        <p role="status" className="text-xs text-text-muted">
          Te estamos llevando a {vendor} para autorizar el acceso…
        </p>
      )}
      {state.status === "success" && (
        <p role="status" className="text-xs font-semibold text-success">
          {successMessage(state.count, label)}
        </p>
      )}
      {state.status === "error" && (
        <SyncErrorAlert
          message={state.message}
          reconnect={state.reconnect}
          providerLabel={label}
          onRetry={() => void calendar.retry()}
        />
      )}
    </div>
  );
}
