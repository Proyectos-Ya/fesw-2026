"use client";

import { useEffect, useState } from "react";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { useWorkspace } from "../WorkspaceContext";
import {
  getWorkspaceMatchThreshold,
  setWorkspaceMatchThreshold,
} from "../services/workspaceService";

interface Props {
  supplierId: string;
}

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; threshold: number | null }
  | { kind: "error"; message: string };

function errorMessage(err: unknown): string {
  if (err instanceof ApiError || err instanceof TimeoutError) return err.message;
  return "No se pudo cargar el umbral de compatibilidad.";
}

export function WorkspaceMatchThresholdSettings({ supplierId }: Props) {
  const { isAdmin } = useWorkspace();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [saving, setSaving] = useState(false);
  const [localPct, setLocalPct] = useState<number>(70);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    void (async () => {
      try {
        const { match_threshold } = await getWorkspaceMatchThreshold(supplierId);
        if (!cancelled) {
          setState({ kind: "ready", threshold: match_threshold });
          if (match_threshold !== null) {
            setLocalPct(Math.round(match_threshold * 100));
          }
        }
      } catch (err) {
        if (!cancelled) setState({ kind: "error", message: errorMessage(err) });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [supplierId]);

  const save = async (threshold: number | null) => {
    setSaving(true);
    try {
      const { match_threshold } = await setWorkspaceMatchThreshold(supplierId, {
        match_threshold: threshold,
      });
      setState({ kind: "ready", threshold: match_threshold });
      if (match_threshold !== null) {
        setLocalPct(Math.round(match_threshold * 100));
      }
    } catch (err) {
      setState({ kind: "error", message: errorMessage(err) });
    } finally {
      setSaving(false);
    }
  };

  if (state.kind === "loading") {
    return (
      <div className="mt-6 rounded-lg border border-border-subtle bg-white p-6 text-center text-sm text-text-muted">
        Cargando umbral del workspace…
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div
        role="alert"
        className="mt-6 rounded-lg border border-danger/20 bg-danger-soft/30 p-4 text-sm text-danger"
      >
        {state.message}
      </div>
    );
  }

  const { threshold } = state;
  const hasOverride = threshold !== null;

  return (
    <div className="mt-6 rounded-lg border border-border-subtle bg-white p-6 shadow-xs">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-text-strong">
          Umbral de compatibilidad del workspace
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          {hasOverride
            ? "Todos los miembros del equipo reciben alertas con este criterio, en vez del suyo individual."
            : "Cada miembro usa su propio umbral de preferencias. Puedes fijar uno único para todo el equipo."}
        </p>
      </div>

      {!hasOverride ? (
        isAdmin ? (
          <div className="flex items-center justify-between gap-4 rounded-lg bg-warm-50 px-4 py-3">
            <span className="text-sm text-text-subtle">Sin override activo</span>
            <Button
              variant="primary"
              isLoading={saving}
              onClick={() => void save(0.7)}
            >
              Fijar umbral del workspace
            </Button>
          </div>
        ) : (
          <div className="rounded-lg bg-warm-50 px-4 py-3 text-sm text-text-subtle">
            Sin override activo — cada miembro usa su umbral personal.
          </div>
        )
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={1}
              max={100}
              step={1}
              value={localPct}
              disabled={saving || !isAdmin}
              onChange={(e) => setLocalPct(Number(e.target.value))}
              onMouseUp={(e) =>
                void save(Number(e.currentTarget.value) / 100)
              }
              onTouchEnd={(e) =>
                void save(Number(e.currentTarget.value) / 100)
              }
              onKeyUp={(e) =>
                void save(Number(e.currentTarget.value) / 100)
              }
              className="flex-1 accent-[var(--primary)]"
              aria-label="Umbral de compatibilidad del workspace"
            />
            <span className="w-16 text-right font-mono text-lg font-semibold text-text-strong">
              {localPct}%
            </span>
          </div>
          {isAdmin && (
            <Button
              variant="ghost"
              isLoading={saving}
              onClick={() => void save(null)}
              className="self-start text-sm"
            >
              Restaurar al umbral individual
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
