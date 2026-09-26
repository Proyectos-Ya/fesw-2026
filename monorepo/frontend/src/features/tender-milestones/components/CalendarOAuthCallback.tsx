"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiError, TimeoutError } from "@/features/shared/api/client";

import { completeCalendarAuthorization } from "../services/calendarService";
import { CALENDAR_PROVIDER_LABELS, type CalendarProvider } from "../types";
import { consumeCalendarReturnTender } from "../utils/calendarReturn";

interface CalendarOAuthCallbackProps {
  provider: CalendarProvider;
  code: string | null;
  state: string | null;
  /** Lo que devuelve el proveedor si el usuario canceló o algo falló de su lado. */
  error: string | null;
}

type Status = { kind: "working" } | { kind: "failed"; message: string; returnHref: string };

export function CalendarOAuthCallback({ provider, code, state, error }: CalendarOAuthCallbackProps) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>({ kind: "working" });
  // El código de autorización es de un solo uso: el doble montaje de StrictMode
  // no debe mandarlo dos veces.
  const started = useRef(false);
  const label = CALENDAR_PROVIDER_LABELS[provider];

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const returnTender = consumeCalendarReturnTender();
    const returnHref = returnTender ? `/matches/${encodeURIComponent(returnTender)}` : "/matches";
    const fail = (message: string) => setStatus({ kind: "failed", message, returnHref });

    if (error) {
      fail(
        error === "access_denied"
          ? `Cancelaste la conexión con ${label}. Tus hitos no se sincronizaron.`
          : `${label} no pudo completar la autorización. Intenta nuevamente.`,
      );
      return;
    }
    if (!code || !state) {
      fail(`No recibimos la autorización de ${label}. Intenta nuevamente desde la licitación.`);
      return;
    }

    completeCalendarAuthorization(provider, code, state)
      .then((result) => {
        router.replace(`/matches/${encodeURIComponent(result.tender_id)}?calendario=${provider}`);
      })
      .catch((err: unknown) => {
        fail(
          err instanceof ApiError || err instanceof TimeoutError
            ? err.message
            : `No se pudo completar la conexión con ${label}.`,
        );
      });
  }, [provider, code, state, error, label, router]);

  if (status.kind === "working") {
    return (
      <p role="status" className="mx-auto mt-16 max-w-md text-center text-sm text-text-muted">
        Conectando con {label}…
      </p>
    );
  }

  return (
    <div className="mx-auto mt-16 max-w-md space-y-4 px-4 text-center">
      <p
        role="alert"
        className="rounded-md border border-danger/20 bg-danger-soft/30 p-4 text-sm font-medium text-danger"
      >
        {status.message}
      </p>
      <Link href={status.returnHref} className="text-sm font-semibold text-primary hover:underline">
        {status.returnHref === "/matches" ? "Volver a mis licitaciones" : "Volver a la licitación"}
      </Link>
    </div>
  );
}
