"use client";

import Link from "next/link";
import { Badge } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { formatClosingDate, formatDateTime } from "@/features/matches/utils/format";
import { useNotifications } from "../hooks/useNotifications";
import type { NotificationItem } from "../notificationTypes";

const UMBRAL_ALTO = 70;
const UMBRAL_MEDIO = 40;

function tonoDelScore(pct: number): "success" | "warning" | "danger" {
  if (pct >= UMBRAL_ALTO) return "success";
  if (pct >= UMBRAL_MEDIO) return "warning";
  return "danger";
}

function NotificationCard({
  item,
  onOpen,
}: {
  item: NotificationItem;
  onOpen: (id: string) => void;
}) {
  const sinLeer = item.read_at === null;

  return (
    <li>
      <Link
        href={`/matches/${item.tender_id}`}
        onClick={() => onOpen(item.id)}
        className={`flex items-start gap-4 rounded-lg border p-4 transition-colors hover:bg-warm-50 ${
          sinLeer
            ? "border-primary/30 bg-primary-soft/20"
            : "border-border-subtle bg-surface-card"
        }`}
      >
        <span
          aria-hidden="true"
          className={`mt-1 flex size-9 flex-none items-center justify-center rounded-full ${
            sinLeer ? "bg-primary-soft" : "bg-warm-100"
          }`}
        >
          <Icon
            name="bell"
            size={18}
            color={sinLeer ? "var(--primary)" : "var(--text-subtle)"}
          />
        </span>

        <span className="flex min-w-0 flex-1 flex-col gap-1.5">
          <span className="flex flex-wrap items-center gap-2">
            <span
              className={`truncate text-sm ${
                sinLeer ? "font-bold text-text-strong" : "font-medium text-text-body"
              }`}
            >
              {item.tender?.name ?? "Licitación no disponible"}
            </span>
            <Badge tone={tonoDelScore(item.score_pct)}>{item.score_pct}%</Badge>
            {/* El criterio pide avisar cuando la licitación de una alerta ya cerró. */}
            {item.is_closed && <Badge tone="neutral">Cerrada</Badge>}
          </span>

          <span className="text-xs text-text-subtle">
            {item.tender?.buyer_name ?? "Organismo no informado"}
            {item.tender && ` · Cierra el ${formatClosingDate(item.tender.closing_at)}`}
          </span>
          <span className="text-xs text-text-subtle">
            Detectada el {formatDateTime(item.created_at)}
          </span>
        </span>

        {sinLeer && (
          <span
            aria-label="Sin leer"
            className="mt-2 size-2 flex-none rounded-full bg-primary"
          />
        )}
      </Link>
    </li>
  );
}

export function NotificationPanel() {
  const { state, retry, markRead, markAllRead } = useNotifications();

  return (
    <section className="mx-auto w-full max-w-4xl">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold text-text-strong">Alertas</h1>
          <p className="mt-1 text-sm text-text-muted">
            Licitaciones nuevas que superan tu umbral de compatibilidad.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/configuracion/notificaciones"
            className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold text-text-muted transition-colors hover:bg-warm-100 hover:text-text-strong"
          >
            <Icon name="settings" size={16} />
            Preferencias
          </Link>
          {state.kind === "ready" && state.items.some((i) => i.read_at === null) && (
            <Button variant="ghost" onClick={() => void markAllRead()}>
              Marcar todo como leído
            </Button>
          )}
        </div>
      </header>

      {state.kind === "loading" && (
        <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center text-sm text-text-muted">
          Cargando alertas…
        </div>
      )}

      {state.kind === "error" && (
        <div
          role="alert"
          className="rounded-lg border border-danger/20 bg-danger-soft/30 p-6 text-center"
        >
          <p className="text-sm font-medium text-danger">{state.message}</p>
          <Button variant="primary" className="mt-4" onClick={retry}>
            Reintentar
          </Button>
        </div>
      )}

      {state.kind === "ready" && state.items.length === 0 && (
        <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center">
          <p className="text-sm font-medium text-text-strong">
            Todavía no hay alertas
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Te avisaremos por correo y acá cuando aparezca una licitación que supere
            tu umbral de compatibilidad.
          </p>
        </div>
      )}

      {state.kind === "ready" && state.items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {state.items.map((item) => (
            <NotificationCard
              key={item.id}
              item={item}
              onOpen={(id) => void markRead(id)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
