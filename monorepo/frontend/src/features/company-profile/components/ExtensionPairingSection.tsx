"use client";

import { useCallback, useEffect, useState } from "react";
import { Puzzle, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/features/shared/components/Button";
import { pairExtension, probeExtension } from "@/features/shared/extension/extensionBridge";

interface ExtensionPairingSectionProps {
  supplierId: string;
}

type PairingStatus = "idle" | "checking" | "not_installed" | "pairing" | "success" | "error";

/**
 * Estado de la extensión en este navegador. La vinculación ocurre sola al postular; aquí
 * solo se ve el estado real (lo confirma la extensión) y se puede re-vincular.
 */
export function ExtensionPairingSection({ supplierId }: ExtensionPairingSectionProps) {
  const [status, setStatus] = useState<PairingStatus>("checking");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const statusFromProbe = (probe: Awaited<ReturnType<typeof probeExtension>>): PairingStatus =>
    !probe.installed ? "not_installed" : probe.paired ? "success" : "idle";

  const refresh = useCallback(async () => {
    setStatus("checking");
    setStatus(statusFromProbe(await probeExtension(1500)));
  }, []);

  // El estado inicial ya es "checking": al montar solo se espera la respuesta.
  useEffect(() => {
    let active = true;
    void probeExtension(1500).then((probe) => {
      if (active) setStatus(statusFromProbe(probe));
    });
    return () => {
      active = false;
    };
  }, []);

  const handlePair = async () => {
    setErrorMessage(null);
    const probe = await probeExtension(1500);
    if (!probe.installed) {
      setStatus("not_installed");
      return;
    }
    setStatus("pairing");
    const res = await pairExtension({ workspaceId: supplierId, extensionVersion: probe.version });
    if (res.ok) {
      setStatus("success");
    } else {
      setStatus("error");
      setErrorMessage(res.error ?? "Error al vincular extensión.");
    }
  };

  return (
    <section className="mt-8 rounded-2xl border border-border bg-surface p-6 shadow-xs">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary">
            <Puzzle className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-text-strong">
              Extensión de Navegador
            </h2>
            <p className="text-xs text-text-subtle">
              Sincroniza bases y anexos oficiales directamente desde Mercado Público.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 border-t border-border pt-4">
        {status === "idle" && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <span className="text-xs text-text-muted">
              Disponible para Google Chrome, Microsoft Edge y Mozilla Firefox.
            </span>
            <Button variant="primary" className="px-3 py-1.5 text-xs" onClick={handlePair}>
              Vincular en este navegador
            </Button>
          </div>
        )}

        {status === "checking" && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <RefreshCw className="h-4 w-4 animate-spin text-primary" />
            <span>Detectando extensión en tu navegador...</span>
          </div>
        )}

        {status === "not_installed" && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-xs font-medium text-warning-text">
              <AlertCircle className="h-4 w-4 text-warning" />
              <span>No detectamos la extensión activa en este navegador.</span>
            </div>
            <p className="text-xs text-text-subtle">
              Asegúrate de haber instalado y habilitado la extensión oficial de Chiripa.
            </p>
            <div className="flex justify-end pt-1">
              <Button variant="primary" className="px-3 py-1.5 text-xs" onClick={() => void refresh()}>
                Volver a intentar
              </Button>
            </div>
          </div>
        )}

        {status === "pairing" && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <RefreshCw className="h-4 w-4 animate-spin text-primary" />
            <span>Vinculando tu cuenta con la extensión...</span>
          </div>
        )}

        {status === "success" && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-medium text-success-text">
              <CheckCircle2 className="h-4 w-4 text-success" />
              <span>¡Extensión vinculada y lista para sincronizar anexos!</span>
            </div>
            <Button variant="ghost" className="px-3 py-1.5 text-xs" onClick={handlePair}>
              Re-vincular
            </Button>
          </div>
        )}

        {status === "error" && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-xs font-medium text-danger-text">
              <AlertCircle className="h-4 w-4 text-danger" />
              <span>{errorMessage || "Ocurrió un error al vincular la extensión."}</span>
            </div>
            <div className="flex justify-end pt-1">
              <Button variant="primary" className="px-3 py-1.5 text-xs" onClick={handlePair}>
                Reintentar
              </Button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
