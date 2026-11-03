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

export function PostulationConfirmDialog({
  open,
  packageData,
  busy,
  onClose,
  onConfirm,
  technicalDocxBase64,
}: PostulationConfirmDialogProps) {
  if (!packageData) return null;

  // Estado local para permitir editar precios y textos antes de enviar
  const [items, setItems] = useState(() =>
    packageData.items.map((it) => ({
      ...it,
      unit_price: it.suggested_unit_price,
    }))
  );

  const [observations, setObservations] = useState(packageData.observations);
  const [validityDays, setValidityDays] = useState(packageData.validity_days || 30);
  const [deliveryDays, setDeliveryDays] = useState(packageData.delivery_term_days || 15);
  const [includeTechnicalDoc, setIncludeTechnicalDoc] = useState(Boolean(technicalDocxBase64));

  const totalClp = useMemo(() => {
    return items.reduce((acc, it) => acc + Math.round(it.quantity * it.unit_price), 0);
  }, [items]);

  const handlePriceChange = (lineNumber: number, newPriceStr: string) => {
    const val = parseInt(newPriceStr.replace(/\D/g, ""), 10) || 0;
    setItems((prev) =>
      prev.map((it) =>
        it.line_number === lineNumber ? { ...it, unit_price: val } : it
      )
    );
  };

  const isObservationsTooLong = observations.length > MAX_OBSERVATIONS_LENGTH;
  const canConfirm = !busy && totalClp > 0 && !isObservationsTooLong;

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
      tender_title: packageData.tender.title,
      company_rut: packageData.company.rut,
      company_name: packageData.company.name,
      contact_name: packageData.company.contact_name,
      contact_email: packageData.company.contact_email,
      contact_phone: packageData.company.contact_phone,
      items: items.map((it) => ({
        line_number: it.line_number,
        name: it.name,
        quantity: it.quantity,
        unit: it.unit,
        unit_price: it.unit_price,
        total_price: Math.round(it.quantity * it.unit_price),
        technical_spec: it.technical_spec,
      })),
      total_clp: totalClp,
      observations: observations.slice(0, MAX_OBSERVATIONS_LENGTH),
      validity_days: validityDays,
      delivery_term_days: deliveryDays,
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
              <p className="text-xs text-text-muted">{packageData.tender.title}</p>
            </div>
            <div className="text-right">
              <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                Empresa postulante
              </span>
              <p className="font-bold text-text-strong">{packageData.company.name}</p>
              <p className="text-xs text-text-muted">RUT {packageData.company.rut}</p>
            </div>
          </div>
        </div>

        {/* Tabla de ítems con precios editables */}
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
                  <th className="p-2">Precio Unit. (CLP)</th>
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
                      <td className="p-2">
                        <input
                          type="text"
                          className="w-24 rounded border border-border-strong px-2 py-1 text-right font-mono text-xs focus:border-primary focus:outline-none"
                          value={it.unit_price}
                          onChange={(e) => handlePriceChange(it.line_number, e.target.value)}
                        />
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
        </div>

        {/* Observaciones con tope de 255 caracteres */}
        <div>
          <div className="flex items-center justify-between">
            <label htmlFor="txtObservacionesDialog" className="block font-semibold text-text-strong">
              Descripción de la oferta (Mercado Público)
            </label>
            <span
              className={`text-xs ${
                isObservationsTooLong ? "font-bold text-danger" : "text-text-muted"
              }`}
            >
              {observations.length}/{MAX_OBSERVATIONS_LENGTH}
            </span>
          </div>
          <textarea
            id="txtObservacionesDialog"
            className="mt-1 w-full rounded-md border border-border-strong p-2 text-xs focus:border-primary focus:outline-none"
            rows={3}
            value={observations}
            onChange={(e) => setObservations(e.target.value)}
          />
          {isObservationsTooLong && (
            <p className="mt-1 text-xs text-danger">
              Supera los {MAX_OBSERVATIONS_LENGTH} caracteres máximos permitidos por Mercado Público.
            </p>
          )}
        </div>

        {/* Plazos */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <label className="block font-semibold text-text-strong">Plazo de entrega (días)</label>
            <input
              type="number"
              min={1}
              className="mt-1 w-full rounded border border-border-strong p-1.5 focus:border-primary focus:outline-none"
              value={deliveryDays}
              onChange={(e) => setDeliveryDays(parseInt(e.target.value, 10) || 1)}
            />
          </div>
          <div>
            <label className="block font-semibold text-text-strong">Validez de la oferta (días)</label>
            <input
              type="number"
              min={1}
              className="mt-1 w-full rounded border border-border-strong p-1.5 focus:border-primary focus:outline-none"
              value={validityDays}
              onChange={(e) => setValidityDays(parseInt(e.target.value, 10) || 1)}
            />
          </div>
        </div>

        {/* Adjunto técnico si está disponible */}
        {technicalDocxBase64 && (
          <div className="rounded-md border border-primary/20 bg-primary-soft/30 p-2.5 text-xs">
            <label className="flex items-center gap-2 font-medium text-text-strong">
              <input
                type="checkbox"
                checked={includeTechnicalDoc}
                onChange={(e) => setIncludeTechnicalDoc(e.target.checked)}
                className="rounded border-border-strong"
              />
              Adjuntar documento técnico generado (.docx)
            </label>
          </div>
        )}

        {/* Advertencia CA8 */}
        <div className="rounded-md bg-warning-bg/40 p-3 text-xs text-warning-text border border-warning-border">
          <p className="font-semibold flex items-center gap-1.5">
            <Icon name="alert-triangle" size={14} />
            Importante antes de confirmar:
          </p>
          <p className="mt-0.5">
            La extensión cargará estos valores y anexos en la pestaña de Mercado Público, pero <strong>nunca enviará la postulación ni aceptará declaraciones juradas por ti</strong>. Debes revisar los campos y hacer el envío manual.
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
