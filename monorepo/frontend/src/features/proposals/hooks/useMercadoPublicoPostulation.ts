"use client";

import { useCallback, useState } from "react";
import { compraAgilFichaUrl } from "@/features/matches/utils/links";
import {
  confirmPostulation,
  focusPostulationTab,
  openPostulationTab,
  probeExtension,
  type PostulationConfirmPayload,
} from "@/features/shared/extension/extensionBridge";
import { getPostulationPackage } from "../services/proposalService";
import type { PostulationPackage } from "../types";

interface UseMercadoPublicoPostulationProps {
  tenderId: string;
  tenderCode?: string | null;
}

export function useMercadoPublicoPostulation({
  tenderId,
  tenderCode,
}: UseMercadoPublicoPostulationProps) {
  const [busy, setBusy] = useState(false);
  const [packageData, setPackageData] = useState<PostulationPackage | null>(null);
  const [showExtensionRequiredDialog, setShowExtensionRequiredDialog] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startPostulation = useCallback(async () => {
    setBusy(true);
    setError(null);

    try {
      // 1. Probar si la extensión está instalada (CA2)
      const probe = await probeExtension(1200);
      if (!probe.installed) {
        setShowExtensionRequiredDialog(true);
        setBusy(false);
        return;
      }

      // 2. Abrir la pestaña de Mercado Público inactiva en background (CA3)
      // Mercado Público no permite cotizar desde el buscador público (buscador.mercadopublico.cl);
      // las cotizaciones de Compra Ágil se responden desde el Escritorio Proveedor (Menu.aspx).
      if (tenderCode) {
        const portalUrl = "https://www.mercadopublico.cl/Portal/Modules/Menu/Menu.aspx";
        await openPostulationTab(tenderCode, portalUrl);
      }

      // 3. Obtener el paquete de postulación desde la API de Chiripa
      const pkg = await getPostulationPackage(tenderId);
      setPackageData(pkg);
      setShowConfirmDialog(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error preparando postulación";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }, [tenderId, tenderCode]);

  const confirm = useCallback(
    async (payload: PostulationConfirmPayload) => {
      setBusy(true);
      setError(null);

      try {
        const res = await confirmPostulation(payload);
        if (res.ok) {
          setShowConfirmDialog(false);
          if (typeof navigator !== "undefined" && navigator.clipboard) {
            try {
              await navigator.clipboard.writeText(payload.tender_code);
            } catch {
              // Si el portapapeles está bloqueado por permisos, continuar sin error
            }
          }
          // Enfocar la pestaña de Mercado Público para que el usuario revise y envíe (CA4, CA8)
          await focusPostulationTab(payload.tender_code);
        } else {
          setError(res.error || "No se pudo transferir el paquete a la extensión.");
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Error al confirmar postulación";
        setError(msg);
      } finally {
        setBusy(false);
      }
    },
    []
  );

  return {
    busy,
    packageData,
    showExtensionRequiredDialog,
    showConfirmDialog,
    error,
    startPostulation,
    confirm,
    setShowExtensionRequiredDialog,
    setShowConfirmDialog,
  };
}
