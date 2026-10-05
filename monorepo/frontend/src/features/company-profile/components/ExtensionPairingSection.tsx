"use client";

import { useState } from "react";
import { Puzzle, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { apiFetch } from "@/features/shared/api/client";
import { crearClienteNavegador } from "@/features/auth/supabase/client";
import { Button } from "@/features/shared/components/Button";

interface ExtensionPairingSectionProps {
  supplierId: string;
}

type PairingStatus = "idle" | "checking" | "not_installed" | "pairing" | "success" | "error";

interface StartPairingResponse {
  pairing_ticket: string;
  expires_in_seconds: number;
}

export function ExtensionPairingSection({ supplierId }: ExtensionPairingSectionProps) {
  const [status, setStatus] = useState<PairingStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handlePair = async () => {
    setStatus("checking");
    setErrorMessage(null);

    const nonce = crypto.randomUUID();
    let extensionDetected = false;

    // 1. Escuchar PONG desde el Content Script Bridge
    const onMessage = async (event: MessageEvent) => {
      if (event.origin && window.location.origin && event.origin !== window.location.origin) return;
      const data = event.data;
      if (data?.target !== "CHIRIPA_WEB") return;

      if (data.type === "PONG" && data.nonce === nonce) {
        extensionDetected = true;
        window.removeEventListener("message", onMessage);
        await proceedWithPairing(data.version);
      }
    };

    window.addEventListener("message", onMessage);

    // Enviar PING
    window.postMessage(
      {
        target: "CHIRIPA_EXTENSION",
        type: "PING",
        nonce,
      },
      window.location.origin
    );

    // Si en 1.5 segundos no responde, asumir que no está instalada
    setTimeout(() => {
      if (!extensionDetected) {
        window.removeEventListener("message", onMessage);
        setStatus("not_installed");
      }
    }, 1500);
  };

  const proceedWithPairing = async (extensionVersion: string) => {
    setStatus("pairing");
    try {
      // 2. Iniciar pairing en backend para obtener ticket
      const userAgent = navigator.userAgent.toLowerCase();
      let browser: "chrome" | "firefox" | "edge" | "safari" | "other" = "chrome";
      if (userAgent.includes("edg/")) browser = "edge";
      else if (userAgent.includes("firefox")) browser = "firefox";
      else if (userAgent.includes("safari") && !userAgent.includes("chrome")) browser = "safari";

      const startRes = await apiFetch<StartPairingResponse>("/extension/pairing/start", {
        method: "POST",
        body: JSON.stringify({
          browser,
          extension_version: extensionVersion || "0.1.0",
        }),
      });

      // 3. Obtener sesión de Supabase
      const supabase = crearClienteNavegador();
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData.session?.access_token;
      const refreshToken = sessionData.session?.refresh_token;

      if (!token) {
        throw new Error("No hay una sesión activa para vincular.");
      }

      // 4. Enviar PAIR_SESSION al Content Script Bridge
      const pairNonce = crypto.randomUUID();

      const onPairSuccess = (event: MessageEvent) => {
        if (event.origin && window.location.origin && event.origin !== window.location.origin) return;
        const data = event.data;
        if (data?.target === "CHIRIPA_WEB" && data.type === "PAIR_SUCCESS" && data.nonce === pairNonce) {
          window.removeEventListener("message", onPairSuccess);
          setStatus("success");
        }
      };

      window.addEventListener("message", onPairSuccess);

      // apiUrl para la extensión: en local apunta a 8000, o vía variable de entorno
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      window.postMessage(
        {
          target: "CHIRIPA_EXTENSION",
          type: "PAIR_SESSION",
          nonce: pairNonce,
          payload: {
            pairing_ticket: startRes.pairing_ticket,
            api_url: apiUrl,
            workspace_id: supplierId,
            access_token: token,
            refresh_token: refreshToken || "",
            timestamp: Date.now(),
          },
        },
        window.location.origin
      );

      // Timeout para confirmar
      setTimeout(() => {
        window.removeEventListener("message", onPairSuccess);
        setStatus((prev) => (prev === "pairing" ? "success" : prev));
      }, 3000);
    } catch (err: unknown) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Error al vincular extensión.");
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
          <div className="flex items-center justify-between">
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
            <div className="flex items-center gap-2 text-xs font-medium text-amber-700">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              <span>No detectamos la extensión activa en este navegador.</span>
            </div>
            <p className="text-xs text-text-subtle">
              Asegúrate de haber instalado y habilitado la extensión oficial de Chiripa.
            </p>
            <div className="flex justify-end pt-1">
              <Button variant="primary" className="px-3 py-1.5 text-xs" onClick={handlePair}>
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
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-700">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>¡Extensión vinculada y lista para sincronizar anexos!</span>
            </div>
            <Button variant="ghost" className="px-3 py-1.5 text-xs" onClick={handlePair}>
              Re-vincular
            </Button>
          </div>
        )}

        {status === "error" && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-xs font-medium text-rose-700">
              <AlertCircle className="h-4 w-4 text-rose-600" />
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
