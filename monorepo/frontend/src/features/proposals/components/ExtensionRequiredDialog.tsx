"use client";

import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";
import { Icon } from "@/features/shared/components/Icon";
import {
  EXTENSION_DISTRIBUTION,
  detectBrowser,
  getExtensionInstallUrl,
  getExtensionZipUrl,
  type SupportedBrowser,
} from "@/features/shared/extension/extensionLinks";

interface ExtensionRequiredDialogProps {
  open: boolean;
  onClose: () => void;
  browser?: SupportedBrowser;
}

/** Las direcciones de ajustes del navegador no se abren desde un enlace: se copian. */
function CopyableAddress({ address }: { address: string }) {
  return (
    <span className="inline-flex items-center gap-1 align-middle">
      <code className="rounded bg-surface-card px-1.5 py-0.5 font-mono text-[11px] text-text-strong">
        {address}
      </code>
      <button
        type="button"
        aria-label={`Copiar ${address}`}
        onClick={() => void navigator.clipboard?.writeText(address)}
        className="rounded p-1 text-text-subtle hover:bg-primary-soft hover:text-primary"
      >
        <Icon name="copy" size={12} />
      </button>
    </span>
  );
}

export function ExtensionRequiredDialog({
  open,
  onClose,
  browser,
}: ExtensionRequiredDialogProps) {
  const currentBrowser = browser ?? detectBrowser();
  const isFirefox = currentBrowser === "firefox";
  const installUrl = getExtensionInstallUrl(currentBrowser);
  const otherZipUrl = getExtensionZipUrl(isFirefox ? "chrome" : "firefox");
  const isZip = EXTENSION_DISTRIBUTION === "zip";
  const browserName = isFirefox ? "Firefox" : "Chrome";

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

        {installUrl ? (
          <div className="rounded-md border border-primary/20 bg-primary-soft/40 p-4">
            <p className="font-semibold text-text-strong">
              {isZip ? `Descarga la extensión para ${browserName}` : "Instala la extensión en 1 clic:"}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <a
                href={installUrl}
                {...(isZip ? { download: "" } : { target: "_blank", rel: "noopener noreferrer" })}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-hover"
              >
                <Icon name={isZip ? "download" : "external-link"} size={16} />
                {isZip ? `Descargar extensión para ${browserName} (.zip)` : "Instalar extensión"}
              </a>
              {isZip && otherZipUrl && (
                <a href={otherZipUrl} download="" className="text-xs font-semibold text-text-link hover:underline">
                  Descargar la versión para {isFirefox ? "Chrome" : "Firefox"}
                </a>
              )}
            </div>

            {isZip && (
              <ol className="mt-4 list-decimal space-y-1.5 pl-5 text-xs text-text-muted">
                {isFirefox ? (
                  <>
                    <li>
                      Abre <CopyableAddress address="about:debugging#/runtime/this-firefox" />
                    </li>
                    <li>
                      Pulsa «Cargar complemento temporal…» y elige el .zip descargado.
                    </li>
                    <li>El complemento temporal se elimina al cerrar Firefox: repite estos pasos al volver a abrirlo.</li>
                  </>
                ) : (
                  <>
                    <li>Descomprime el .zip en una carpeta.</li>
                    <li>
                      Abre <CopyableAddress address="chrome://extensions" /> y activa el «Modo de desarrollador».
                    </li>
                    <li>Pulsa «Cargar descomprimida» y elige esa carpeta.</li>
                  </>
                )}
              </ol>
            )}
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
            Las extensiones recién instaladas necesitan que recargues la pestaña abierta para poder
            activarse.
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
