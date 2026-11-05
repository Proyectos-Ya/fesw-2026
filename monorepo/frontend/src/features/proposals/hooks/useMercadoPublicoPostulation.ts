"use client";

import { useCallback, useState } from "react";
import { compraAgilCotizacionUrl, isCompraAgilCode } from "@/features/matches/utils/links";
import {
  confirmPostulation,
  focusPostulationTab,
  openPostulationTab,
  pairExtension,
  probeExtension,
  type PostulationConfirmPayload,
} from "@/features/shared/extension/extensionBridge";
import { downloadTechnicalDocument, getPostulationPackage } from "../services/proposalService";
import type { PostulationPackage } from "../types";

async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

/** Si la descarga falla, se postula igual sin el anexo. */
async function loadTechnicalDocx(tenderId: string): Promise<string | null> {
  try {
    const { blob } = await downloadTechnicalDocument(tenderId);
    return await blobToBase64(blob);
  } catch {
    return null;
  }
}

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
  const [pairingRequired, setPairingRequired] = useState(false);
  const [technicalDocxBase64, setTechnicalDocxBase64] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const postulationUrl = tenderCode
    ? isCompraAgilCode(tenderCode)
      ? compraAgilCotizacionUrl(tenderCode)
      : "https://www.mercadopublico.cl/Portal/Modules/Menu/Menu.aspx"
    : null;

  // Abre la pestaña de MP y prepara el paquete; requiere la extensión vinculada.
  const continueWithPairedExtension = useCallback(async () => {
    // 2. Abrir la pestaña de Mercado Público inactiva en background (CA3)
    // Compra Ágil se cotiza en su ficha (resumen-cotizacion); el buscador público no
    // permite cotizar. Las licitaciones siguen por el Escritorio Proveedor (Menu.aspx).
    if (tenderCode && postulationUrl) {
      await openPostulationTab(tenderCode, postulationUrl);
    }

    // 3. Obtener el paquete de postulación desde la API de Chiripa
    const pkg = await getPostulationPackage(tenderId);
    setPackageData(pkg);
    // El borrador de postulación (documento técnico) va como anexo si existe.
    setTechnicalDocxBase64(pkg.technical_document_available ? await loadTechnicalDocx(tenderId) : null);
    setShowConfirmDialog(true);
  }, [tenderId, tenderCode, postulationUrl]);

  const run = useCallback(
    async (step: () => Promise<void>) => {
      setBusy(true);
      setError(null);
      try {
        await step();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Error preparando postulación";
        setError(msg);
      } finally {
        setBusy(false);
      }
    },
    []
  );

  const startPostulation = useCallback(
    () =>
      run(async () => {
        // 1. Probar si la extensión está instalada (CA2)
        const probe = await probeExtension(1200);
        if (!probe.installed) {
          setShowExtensionRequiredDialog(true);
          return;
        }

        // Vinculación automática: el estado lo confirma la extensión, no se supone.
        if (!probe.paired) {
          const paired = await pairExtension({ extensionVersion: probe.version });
          if (!paired?.ok) {
            setPairingRequired(true);
            return;
          }
        }

        setPairingRequired(false);
        await continueWithPairedExtension();
      }),
    [run, continueWithPairedExtension]
  );

  /** «Vincular»: reintenta la vinculación y, si funciona, sigue con la postulación. */
  const pairAndContinue = useCallback(
    () =>
      run(async () => {
        const paired = await pairExtension();
        if (!paired?.ok) {
          setError(paired?.error ?? "No se pudo vincular la extensión.");
          return;
        }
        setPairingRequired(false);
        await continueWithPairedExtension();
      }),
    [run, continueWithPairedExtension]
  );

  /** «Postular manualmente»: abre Mercado Público sin llenado asistido. */
  const postManually = useCallback(() => {
    setPairingRequired(false);
    if (postulationUrl) window.open(postulationUrl, "_blank", "noopener,noreferrer");
  }, [postulationUrl]);

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
    technicalDocxBase64,
    pairingRequired,
    pairAndContinue,
    retry: startPostulation,
    postManually,
    setPairingRequired,
    confirm,
    setShowExtensionRequiredDialog,
    setShowConfirmDialog,
  };
}
