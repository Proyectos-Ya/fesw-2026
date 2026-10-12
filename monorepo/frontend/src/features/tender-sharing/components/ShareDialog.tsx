"use client";

import { useEffect, useRef, useState } from "react";

import { formatDateTime } from "@/features/matches/utils/format";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";

import { createShareLink, listShareLinks, revokeShareLink } from "../services/sharingService";
import type { CreatedShareLink, ShareLink } from "../types";

interface ShareDialogProps {
  open: boolean;
  tenderId: string;
  onClose: () => void;
}

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof ApiError || error instanceof TimeoutError ? error.message : fallback;
}

/**
 * Compartir la licitación con un enlace de 7 días (HdU 19, criterios 1 y 7).
 *
 * La URL completa solo existe en la respuesta de creación —en la base queda su
 * hash—, así que se muestra una vez y la lista de vigentes solo informa fechas.
 */
export function ShareDialog({ open, tenderId, onClose }: ShareDialogProps) {
  const [links, setLinks] = useState<ShareLink[]>([]);
  const [created, setCreated] = useState<CreatedShareLink | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const titleId = "share-dialog-title";
  const firstButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    listShareLinks(tenderId)
      .then((data) => {
        if (!cancelled) setLinks(data);
      })
      .catch(() => {
        // La lista es secundaria: generar un enlace sigue funcionando sin ella.
      });
    return () => {
      cancelled = true;
    };
  }, [open, tenderId]);

  // Solo al abrir: si dependiera de `onClose`, que suele llegar como función
  // nueva en cada render, le quitaría el foco al usuario a cada rato.
  useEffect(() => {
    if (open) firstButtonRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const create = async () => {
    setIsCreating(true);
    setError(null);
    setCopied(false);
    try {
      const nuevo = await createShareLink(tenderId);
      setCreated(nuevo);
      setLinks((actuales) => [
        { id: nuevo.id, created_at: nuevo.created_at, expires_at: nuevo.expires_at },
        ...actuales,
      ]);
    } catch (err: unknown) {
      setError(messageFrom(err, "No se pudo generar el enlace."));
    } finally {
      setIsCreating(false);
    }
  };

  const copy = async () => {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.url);
      setCopied(true);
    } catch {
      setError("No se pudo copiar. Selecciona el enlace y cópialo a mano.");
    }
  };

  const revoke = async (linkId: string) => {
    setRevokingId(linkId);
    setError(null);
    try {
      await revokeShareLink(tenderId, linkId);
      setLinks((actuales) => actuales.filter((link) => link.id !== linkId));
      if (created?.id === linkId) setCreated(null);
    } catch (err: unknown) {
      setError(messageFrom(err, "No se pudo revocar el enlace. Inténtalo de nuevo."));
    } finally {
      setRevokingId(null);
      setConfirmingId(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div className="w-full max-w-lg rounded-xl border border-border-subtle bg-surface-card p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-border-subtle pb-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-lg bg-primary-soft text-primary">
              <Icon name="share-2" size={18} />
            </span>
            <div>
              <h2 id={titleId} className="text-base font-bold text-text-strong">
                Compartir licitación
              </h2>
              <p className="text-xs text-text-subtle">
                Quien tenga el enlace verá el detalle y el análisis, sin crear una cuenta.
              </p>
            </div>
          </div>
          <button
            ref={firstButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
            className="cursor-pointer rounded-lg p-1.5 text-text-subtle transition-colors hover:bg-warm-100 hover:text-text-strong"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="mt-4 space-y-4">
          {error && (
            <p role="alert" className="rounded-lg bg-danger-soft p-3 text-xs font-medium text-danger">
              {error}
            </p>
          )}

          {created ? (
            <div className="space-y-2 rounded-lg border border-primary/20 bg-primary-soft/30 p-3">
              <label htmlFor="share-url" className="block text-xs font-semibold text-text-strong">
                Enlace para compartir
              </label>
              <div className="flex gap-2">
                <input
                  id="share-url"
                  readOnly
                  value={created.url}
                  onFocus={(event) => event.currentTarget.select()}
                  className="min-w-0 flex-1 rounded-md border border-border-subtle bg-white px-3 py-2 font-mono text-xs text-text-strong"
                />
                <Button type="button" onClick={() => void copy()} className="shrink-0 px-3 py-2">
                  <Icon name={copied ? "check" : "copy"} size={14} />
                  {copied ? "Copiado" : "Copiar enlace"}
                </Button>
              </div>
              <p className="text-xs text-text-muted">
                Vigente hasta el {formatDateTime(created.expires_at)}. Cópialo ahora: por
                seguridad, no se vuelve a mostrar.
              </p>
            </div>
          ) : (
            <Button type="button" onClick={() => void create()} isLoading={isCreating} className="w-full">
              <Icon name="link" size={15} />
              Generar enlace (válido 7 días)
            </Button>
          )}

          {links.length > 0 && (
            <div>
              <h3 className="mb-2 text-[10px] font-bold uppercase tracking-caps text-text-subtle">
                Enlaces vigentes
              </h3>
              <ul aria-label="Enlaces vigentes" className="divide-y divide-border-subtle rounded-lg border border-border-subtle">
                {links.map((link) => (
                  <li key={link.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-xs">
                    <span className="text-text-body">
                      Creado el {formatDateTime(link.created_at)} · Vence el{" "}
                      {formatDateTime(link.expires_at)}
                    </span>
                    {confirmingId === link.id ? (
                      <span className="flex items-center gap-2">
                        <span className="text-text-muted">¿Revocar? Dejará de funcionar al instante.</span>
                        <button
                          type="button"
                          onClick={() => void revoke(link.id)}
                          disabled={revokingId === link.id}
                          className="cursor-pointer rounded-md bg-danger px-2 py-1 font-semibold text-white disabled:opacity-50"
                        >
                          Sí, revocar
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmingId(null)}
                          className="cursor-pointer rounded-md px-2 py-1 text-text-muted hover:bg-warm-100"
                        >
                          Cancelar
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setConfirmingId(link.id)}
                        aria-label={`Revocar el enlace que vence el ${formatDateTime(link.expires_at)}`}
                        className="cursor-pointer rounded-md px-2 py-1 font-semibold text-danger hover:bg-danger-soft"
                      >
                        Revocar
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
