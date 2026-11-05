"use client";

import { useMemo, useState } from "react";
import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";
import { Icon } from "@/features/shared/components/Icon";
import type { PostulationConfirmPayload, PostulationFilePayload } from "@/features/shared/extension/extensionBridge";
import type { PostulationPackage } from "../types";

const MAX_OBSERVATIONS_LENGTH = 255;

interface PostulationConfirmDialogProps {
  open: boolean;
  packageData: PostulationPackage | null;
  busy: boolean;
  onClose: () => void;
  onConfirm: (payload: PostulationConfirmPayload) => void;
  technicalDocxBase64?: string | null;
}

export function PostulationConfirmDialog(props: PostulationConfirmDialogProps) {
  if (!props.packageData) return null;
  return <PostulationConfirmDialogContent {...props} packageData={props.packageData} />;
}

// Los hooks viven aquí para no llamarlos después del return anticipado de arriba.
function PostulationConfirmDialogContent({
  open,
  packageData,
  busy,
  onClose,
  onConfirm,
  technicalDocxBase64,
}: PostulationConfirmDialogProps & { packageData: PostulationPackage }) {

  const rawObservations = packageData.observations ?? packageData.offer_description ?? "";
  const companyName =
    packageData.company.name ||
    packageData.company.trade_name ||
    packageData.company.legal_name ||
    "";
  const tenderTitle = packageData.tender.title || packageData.tender.name || "";

  // Datos derivados y cargados automáticamente desde la postulación y cotización
  const items = useMemo(
    () =>
      packageData.items.map((it, idx) => {
        const unitPrice =
          typeof it.unit_price === "number"
            ? it.unit_price
            : typeof it.suggested_unit_price === "number"
            ? it.suggested_unit_price
            : 0;
        return {
          line_number: it.line_number ?? it.position ?? idx + 1,
          product_code: it.product_code ?? null,
          name: it.name,
          quantity: it.quantity,
          unit: it.unit ?? it.unit_of_measure ?? "UN",
          unit_price: unitPrice,
          technical_spec: it.technical_spec ?? it.description ?? "",
        };
      }),
    [packageData.items]
  );

  const validityDays = packageData.validity_days || 30;
  const deliveryDays = packageData.delivery_term_days || 15;
  // Marcado por defecto: el documento puede llegar después de montar el diálogo.
  const [includeTechnicalDoc, setIncludeTechnicalDoc] = useState(true);
  const [rigorouslyReviewed, setRigorouslyReviewed] = useState(false);

  const totalClp = useMemo(() => {
    return items.reduce((acc, it) => acc + Math.round(it.quantity * it.unit_price), 0);
  }, [items]);

  const canConfirm = !busy && totalClp > 0 && rigorouslyReviewed;

  const handleConfirm = () => {
    if (!canConfirm) return;

    const files: PostulationFilePayload[] = [];
    if (includeTechnicalDoc && technicalDocxBase64) {
      files.push({
        name: `oferta_tecnica_${packageData.tender.code}.docx`,
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size: Math.round((technicalDocxBase64.length * 3) / 4),
        data_base64: technicalDocxBase64,
      });
    }

    const payload: PostulationConfirmPayload = {
      tender_code: packageData.tender.code,
      tender_title: tenderTitle,
      company_rut: packageData.company.rut,
      company_name: companyName,
      contact_name: packageData.company.contact_name,
      contact_email: packageData.company.contact_email,
      contact_phone: packageData.company.contact_phone,
      items: items.map((it) => ({
        line_number: it.line_number,
        product_code: it.product_code,
        name: it.name,
        quantity: it.quantity,
        unit: it.unit,
        unit_price: it.unit_price,
        total_price: Math.round(it.quantity * it.unit_price),
        technical_spec: it.technical_spec,
      })),
      total_clp: totalClp,
      observations: rawObservations.slice(0, MAX_OBSERVATIONS_LENGTH),
      validity_days: validityDays,
      delivery_term_days: deliveryDays,
      shipping_clp: packageData.shipping_clp ?? null,
      files,
    };

    onConfirm(payload);
  };

  const formattedTotal = new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(totalClp);

  return (
    <Dialog
      open={open}
      title="Confirmar postulación en Mercado Público"
      onClose={onClose}
    >
      <div className="flex flex-col gap-4 text-sm text-text-body">
        {/* Info cabecera */}
        <div className="rounded-md border border-border-subtle bg-surface-inset p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                Licitación
              </span>
              <p className="font-bold text-text-strong">{packageData.tender.code}</p>
              <p className="text-xs text-text-muted">{tenderTitle}</p>
            </div>
            <div className="text-right">
              <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                Empresa postulante
              </span>
              <p className="font-bold text-text-strong">{companyName}</p>
              <p className="text-xs text-text-muted">RUT {packageData.company.rut}</p>
            </div>
          </div>
        </div>

        {/* Tabla de ítems cotizados (modo lectura / verificación) */}
        <div>
          <label className="mb-1 block font-semibold text-text-strong">
            Precios cotizados por ítem
          </label>
          <div className="max-h-48 overflow-y-auto rounded-md border border-border-subtle">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-inset font-semibold text-text-muted">
                <tr>
                  <th className="p-2">#</th>
                  <th className="p-2">Descripción</th>
                  <th className="p-2">Cant.</th>
                  <th className="p-2 text-right">Precio Unit. (CLP)</th>
                  <th className="p-2 text-right">Subtotal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {items.map((it) => {
                  const subtotal = Math.round(it.quantity * it.unit_price);
                  return (
                    <tr key={it.line_number}>
                      <td className="p-2 text-text-muted">{it.line_number}</td>
                      <td className="p-2 font-medium text-text-strong">{it.name}</td>
                      <td className="p-2">{it.quantity} {it.unit}</td>
                      <td className="p-2 text-right font-mono font-medium text-text-strong">
                        ${it.unit_price.toLocaleString("es-CL")}
                      </td>
                      <td className="p-2 text-right font-mono font-medium text-text-strong">
                        ${subtotal.toLocaleString("es-CL")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-2 flex items-center justify-between px-1">
            <span className="text-xs text-text-muted">Total neto cotizado:</span>
            <span className="text-base font-bold text-primary">{formattedTotal}</span>
          </div>

          {totalClp === 0 && (
            <p className="mt-1 text-xs text-danger font-medium">
              Falta ingresar precios en la cotización. Vuelve al Paso 1 (Cotización y Borrador) para indicar los valores antes de confirmar.
            </p>
          )}
        </div>

        {/* Descripción de la oferta (modo lectura) */}
        <div>
          <span className="mb-1 block font-semibold text-text-strong">
            Descripción de la oferta (Mercado Público)
          </span>
          <div className="rounded-md border border-border-subtle bg-surface-inset p-2.5 text-xs text-text-body max-h-24 overflow-y-auto whitespace-pre-wrap leading-relaxed">
            {rawObservations || "Sin descripción"}
          </div>
        </div>

        {/* Plazos de entrega y validez */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-md border border-border-subtle bg-surface-inset p-2.5">
            <span className="text-text-muted block text-[11px]">Plazo de entrega</span>
            <p className="font-semibold text-text-strong mt-0.5">{deliveryDays} días</p>
          </div>
          <div className="rounded-md border border-border-subtle bg-surface-inset p-2.5">
            <span className="text-text-muted block text-[11px]">Validez de la oferta</span>
            <p className="font-semibold text-text-strong mt-0.5">{validityDays} días</p>
          </div>
        </div>

        {/* Adjunto técnico si está disponible */}
        {technicalDocxBase64 && (
          <div className="rounded-md border border-primary/20 bg-primary-soft/30 p-2.5 text-xs">
            <label className="flex items-center gap-2 font-medium text-text-strong cursor-pointer">
              <input
                type="checkbox"
                checked={includeTechnicalDoc}
                onChange={(e) => setIncludeTechnicalDoc(e.target.checked)}
                className="rounded border-border-strong text-primary focus:ring-primary"
              />
              Adjuntar documento técnico generado (.docx)
            </label>
          </div>
        )}

        {/* Checkbox de revisión rigurosa */}
        <label className="flex items-start gap-2.5 rounded-md border border-primary/30 bg-primary-soft/40 p-3 text-xs cursor-pointer select-none">
          <input
            type="checkbox"
            id="chkRevisionRigurosa"
            checked={rigorouslyReviewed}
            onChange={(e) => setRigorouslyReviewed(e.target.checked)}
            className="mt-0.5 size-4 rounded border-border-strong text-primary focus:ring-primary cursor-pointer"
          />
          <span className="text-text-strong leading-snug">
            <strong>He revisado rigurosamente</strong> los montos cotizados, los plazos, la descripción y los antecedentes adjuntos antes de transferir a Mercado Público.
          </span>
        </label>

        {/* Advertencia CA8 */}
        <div className="rounded-md bg-warning-bg/40 p-3 text-xs text-warning-text border border-warning-border">
          <p className="font-semibold flex items-center gap-1.5">
            <Icon name="alert-triangle" size={14} />
            Importante para postular en Mercado Público:
          </p>
          <p className="mt-1">
            Al confirmar, la extensión abrirá tu <strong>Escritorio de Proveedor</strong> en Mercado Público y copiará el código <strong>{packageData.tender.code}</strong> a tu portapapeles.
          </p>
          <p className="mt-1">
            En Mercado Público ve a <strong>Compra Ágil</strong>, pega el código en el buscador y presiona <strong>&quot;Participar&quot;</strong> o <strong>&quot;Responder&quot;</strong>. La extensión autocompletará los valores, pero <strong>nunca enviará la oferta ni aceptará declaraciones juradas por ti</strong>.
          </p>
        </div>

        {/* Acciones */}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            onClick={handleConfirm}
            disabled={!canConfirm}
          >
            {busy ? (
              <>
                <Icon name="refresh-cw" size={14} className="animate-spin" />
                Cargando...
              </>
            ) : (
              <>
                <Icon name="check" size={14} />
                Confirmar y Cargar en Mercado Público
              </>
            )}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
