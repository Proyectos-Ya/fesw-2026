"use client";

/* eslint-disable react-hooks/set-state-in-effect -- la carga inicial usa el patrón canónico de efecto + flag de cancelación, igual que el resto de la app. */

import { useEffect, useState } from "react";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { Switch } from "@/features/shared/components/Switch";
import { formatDateTime } from "@/features/matches/utils/format";
import type {
  DeliveryMode,
  NotificationPreferences,
} from "../notificationTypes";
import {
  getNotificationPreferences,
  reactivateEmailDelivery,
  updateNotificationPreferences,
} from "../services/notificationService";
import { DeliveryOutbox } from "./DeliveryOutbox";

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; preferences: NotificationPreferences }
  | { kind: "error"; message: string };

const MODOS: ReadonlyArray<{ value: DeliveryMode; label: string; hint: string }> = [
  {
    value: "immediate",
    label: "Aviso inmediato",
    hint: "Un correo apenas detectamos una licitación compatible.",
  },
  {
    value: "daily_digest",
    label: "Resumen diario",
    hint: "Un solo correo al día con todo lo detectado.",
  },
];

function mensajeDeError(err: unknown): string {
  if (err instanceof ApiError || err instanceof TimeoutError) return err.message;
  return "No pudimos cargar tus preferencias.";
}

export function NotificationSettings() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [saving, setSaving] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    void (async () => {
      try {
        const preferences = await getNotificationPreferences();
        if (!cancelled) setState({ kind: "ready", preferences });
      } catch (err) {
        if (!cancelled) setState({ kind: "error", message: mensajeDeError(err) });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [retryNonce]);

  const guardar = async (cambio: Parameters<typeof updateNotificationPreferences>[0]) => {
    setSaving(true);
    try {
      const preferences = await updateNotificationPreferences(cambio);
      setState({ kind: "ready", preferences });
    } catch (err) {
      setState({ kind: "error", message: mensajeDeError(err) });
    } finally {
      setSaving(false);
    }
  };

  const reactivar = async () => {
    setSaving(true);
    try {
      const preferences = await reactivateEmailDelivery();
      setState({ kind: "ready", preferences });
    } catch (err) {
      setState({ kind: "error", message: mensajeDeError(err) });
    } finally {
      setSaving(false);
    }
  };

  if (state.kind === "loading") {
    return (
      <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center text-sm text-text-muted">
        Cargando preferencias…
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div
        role="alert"
        className="rounded-lg border border-danger/20 bg-danger-soft/30 p-6 text-center"
      >
        <p className="text-sm font-medium text-danger">{state.message}</p>
        <Button
          variant="primary"
          className="mt-4"
          onClick={() => setRetryNonce((n) => n + 1)}
        >
          Reintentar
        </Button>
      </div>
    );
  }

  const { preferences } = state;

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header>
        <h1 className="font-display text-2xl font-bold text-text-strong">
          Preferencias de alertas
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Decide cuándo avisarte y con qué nivel de compatibilidad.
        </p>
      </header>

      {/* Criterio: si el correo del usuario rebotó, el sistema desactiva el
          envío y tiene que decírselo en su sección de notificaciones. */}
      {!preferences.email_delivery_enabled && (
        <div
          role="alert"
          className="rounded-lg border border-danger/20 bg-danger-soft/30 p-4"
        >
          <div className="flex items-start gap-3">
            <Icon name="triangle-alert" size={18} color="var(--danger)" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-danger">
                Desactivamos el envío de correos a tu dirección
              </p>
              <p className="mt-1 text-sm text-text-body">
                {preferences.last_failure_reason ??
                  "El servicio de correo rechazó tu dirección."}
                {preferences.last_failure_at &&
                  ` (${formatDateTime(preferences.last_failure_at)})`}
              </p>
              <p className="mt-1 text-xs text-text-subtle">
                Seguirás viendo las alertas en la plataforma. Corrige tu correo y
                vuelve a activarlo.
              </p>
              <Button
                variant="primary"
                className="mt-3"
                isLoading={saving}
                onClick={() => void reactivar()}
              >
                Reactivar envío de correos
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-lg border border-border-subtle bg-surface-card p-6">
        <Switch
          checked={preferences.enabled}
          disabled={saving}
          onChange={(enabled) => void guardar({ enabled })}
          label="Alertas de nuevas licitaciones"
          description="Recibe un aviso cuando aparezca una licitación compatible con tu empresa."
        />
      </div>

      <div className="rounded-lg border border-border-subtle bg-surface-card p-6">
        <label
          htmlFor="umbral"
          className="text-sm font-semibold text-text-strong"
        >
          Umbral de compatibilidad
        </label>
        <p className="mt-1 text-xs text-text-subtle">
          Solo te avisaremos de licitaciones con una compatibilidad igual o superior
          a este valor. El verde de la plataforma empieza en 70%.
        </p>
        <div className="mt-4 flex items-center gap-4">
          <input
            id="umbral"
            type="range"
            min={1}
            max={100}
            step={1}
            value={preferences.threshold_pct}
            disabled={saving || !preferences.enabled}
            onChange={(e) =>
              setState({
                kind: "ready",
                preferences: {
                  ...preferences,
                  threshold_pct: Number(e.target.value),
                },
              })
            }
            // Se guarda al soltar y no en cada píxel: arrastrar el control
            // dispararía una petición por cada valor intermedio.
            onMouseUp={(e) =>
              void guardar({ threshold_pct: Number(e.currentTarget.value) })
            }
            onTouchEnd={(e) =>
              void guardar({ threshold_pct: Number(e.currentTarget.value) })
            }
            onKeyUp={(e) =>
              void guardar({ threshold_pct: Number(e.currentTarget.value) })
            }
            className="flex-1 accent-[var(--primary)]"
          />
          <span className="w-16 text-right font-mono text-lg font-semibold text-text-strong">
            {preferences.threshold_pct}%
          </span>
        </div>
      </div>

      <fieldset className="rounded-lg border border-border-subtle bg-surface-card p-6">
        <legend className="px-1 text-sm font-semibold text-text-strong">
          Frecuencia
        </legend>
        <div className="mt-2 flex flex-col gap-3">
          {MODOS.map((modo) => (
            <label
              key={modo.value}
              className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors ${
                preferences.delivery_mode === modo.value
                  ? "border-primary bg-primary-soft/20"
                  : "border-border-subtle hover:bg-warm-50"
              }`}
            >
              <input
                type="radio"
                name="delivery_mode"
                value={modo.value}
                checked={preferences.delivery_mode === modo.value}
                disabled={saving || !preferences.enabled}
                onChange={() => void guardar({ delivery_mode: modo.value })}
                className="mt-1 accent-[var(--primary)]"
              />
              <span className="flex flex-col gap-0.5">
                <span className="text-sm font-semibold text-text-strong">
                  {modo.label}
                </span>
                <span className="text-xs text-text-subtle">{modo.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <DeliveryOutbox />
    </section>
  );
}
