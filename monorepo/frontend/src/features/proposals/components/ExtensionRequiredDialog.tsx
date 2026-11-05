"use client";

import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";
import { Icon } from "@/features/shared/components/Icon";
import {
  detectBrowser,
  getExtensionStoreUrl,
  type SupportedBrowser,
} from "@/features/shared/extension/extensionLinks";

interface ExtensionRequiredDialogProps {
  open: boolean;
  onClose: () => void;
  browser?: SupportedBrowser;
}

export function ExtensionRequiredDialog({
  open,
  onClose,
  browser,
}: ExtensionRequiredDialogProps) {
  const currentBrowser = browser ?? detectBrowser();
  const storeUrl = getExtensionStoreUrl(currentBrowser);

  const handleReload = () => {
    if (typeof window !== "undefined") {
      window.location.reload();
    }
  };

  return (
    <Dialog open={open} title="Necesitas la extensión de Chiripa" onClose={onClose}>
      <div className="flex flex-col gap-4 text-sm text-text-body">
        <p>
          Para cargar automáticamente los datos, cotizaciones y anexos en Mercado Público sin
          tipearlos a mano, necesitas tener instalada la extensión oficial de Chiripa en tu
          navegador.
        </p>

        {storeUrl ? (
          <div className="rounded-md border border-primary/20 bg-primary-soft/40 p-4">
            <p className="font-semibold text-text-strong">Instala la extensión en 1 clic:</p>
            <p className="mt-1 text-xs text-text-muted">
              Disponible para {currentBrowser === "firefox" ? "Firefox" : "Google Chrome y Microsoft Edge"}.
            </p>
            <div className="mt-3">
              <a
                href={storeUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-hover"
              >
                <Icon name="external-link" size={16} />
                Instalar extensión
              </a>
            </div>
          </div>
        ) : (
          <div className="rounded-md border border-warning-border bg-warning-bg/40 p-4">
            <p className="font-semibold text-warning-text">Navegador no soportado directamente</p>
            <p className="mt-1 text-xs text-text-muted">
              La postulación asistida requiere un navegador compatible con extensiones (Google Chrome, Microsoft Edge, Brave o Firefox en escritorio).
            </p>
          </div>
        )}

        <div className="rounded-md bg-surface-inset p-3 text-xs text-text-muted">
          <p className="font-semibold text-text-strong">¿Ya la instalaste?</p>
          <p className="mt-0.5">
            Por seguridad de Chromium, las extensiones recién instaladas necesitan que recargues la
            pestaña abierta para poder activarse.
          </p>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>
            Cerrar
          </Button>
          <Button variant="primary" onClick={handleReload}>
            <Icon name="refresh-cw" size={14} />
            Ya la instalé — Recargar
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
