"use client";

import { useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { type TenderMaterial, type Material, type Quotation, materialsFromTender, subtotal, total, validate, toCsv } from "./quotation";

const blank = (): Material => ({ description: "", unit: "", quantity: "", unit_price: "" });
const currency = "CLP" as const;
const noTenderItems: TenderMaterial[] = [];
interface QuotationEditorProps { tenderId: string; tenderCode: string; tenderItems?: TenderMaterial[]; }
type Row = Material & { key: string };
const row = (item: Material): Row => ({ ...item, key: crypto.randomUUID() });

export function QuotationEditor({ tenderId, tenderCode, tenderItems = noTenderItems }: QuotationEditorProps) {
  const [open, setOpen] = useState(false);
  const [opened, setOpened] = useState(false);
  return <section className="mb-6 rounded-lg border border-border-subtle bg-surface-card p-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-lg font-bold text-text-strong">Cotización de materiales</h2>
        <p className="text-sm text-text-muted">Estima los costos de esta licitación y descarga tu cotización.</p></div>
      <Button onClick={() => { setOpened(true); setOpen(!open); }} aria-expanded={open}>{open ? "Cerrar cotización" : "Generar cotización"}</Button>
    </div>
    {opened && <div hidden={!open}><QuotationForm key={tenderId} tenderId={tenderId} tenderCode={tenderCode} tenderItems={tenderItems} /></div>}
  </section>;
}

function QuotationForm({ tenderId, tenderCode, tenderItems = noTenderItems }: QuotationEditorProps) {
  const [items, setItems] = useState<Row[]>([]);
  const [initialTenderItems] = useState(tenderItems);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [dirty, setDirty] = useState(false);
  const endpoint = `/tenders/${tenderId}/quotation`;

  useEffect(() => {
    let cancelled = false;
    apiFetch<Quotation>(endpoint).then(data => {
      if (cancelled) return;
      if (data.currency !== "CLP") {
        setLoadError(`La cotización guardada está en ${data.currency}. No se puede convertir a CLP sin revisar sus precios.`);
        return;
      }
      setItems(data.items.map(row));
    }).catch((error: unknown) => {
      if (cancelled) return;
      if (error instanceof ApiError && error.status === 404) {
        const materials = materialsFromTender(initialTenderItems);
        setItems((materials.length ? materials : [blank()]).map(row));
      }
      else setLoadError(error instanceof Error ? error.message : "No se pudo cargar la cotización.");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [endpoint, attempt, initialTenderItems]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function changed() { setDirty(true); setMessage(""); setErrors([]); }
  function update(key: string, field: keyof Material, value: string) {
    changed(); setItems(items.map(item => item.key === key ? { ...item, [field]: value } : item));
  }

  async function save(download: boolean) {
    const data = items.map(({ description, unit, quantity, unit_price }) => ({ description: description.trim(), unit: unit.trim(), quantity, unit_price }));
    const invalid = validate(data);
    setErrors(invalid); setMessage("");
    if (invalid.length) return;
    setBusy(true);
    try {
      const saved = await apiFetch<Quotation>(endpoint, { method: "PUT", body: JSON.stringify({ currency, items: data }) });
      setDirty(false);
      if (download) {
        const csv = toCsv(saved.items, saved.currency, tenderCode, saved.supplier_id);
        const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
        const link = document.createElement("a");
        link.href = url; link.download = `cotizacion-${tenderCode.replace(/[^a-zA-Z0-9_-]/g, "_")}.csv`;
        document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
      setMessage(download ? "Cotización guardada y descargada." : "Cotización guardada.");
    } catch (error: unknown) {
      setErrors([error instanceof Error ? error.message : "No se pudo guardar. Intenta nuevamente."]);
    } finally { setBusy(false); }
  }

  if (loading) return <p role="status" className="mt-4">Cargando cotización…</p>;
  if (loadError) return <div className="mt-4"><p role="alert">{loadError}</p><Button onClick={() => { setLoading(true); setLoadError(""); setAttempt(attempt + 1); }}>Reintentar</Button></div>;
  const inputClass = "mt-1 w-full rounded-md border border-border-subtle bg-surface-card p-2 text-text-strong";
  return <form className="mt-6 space-y-4" noValidate onSubmit={event => { event.preventDefault(); void save(false); }}>
    <fieldset disabled={busy} className="space-y-4">
      <p className="text-sm text-text-muted">Completa las cantidades y los precios unitarios en pesos chilenos (CLP). Revisa la unidad de medida. Puedes editar los materiales o agregar los que falten. Total sin impuestos ni recargos.</p>
      {!materialsFromTender(initialTenderItems).length && <p className="text-sm text-text-muted">La licitación no tiene materiales detallados. Agrégalos manualmente según sus especificaciones.</p>}
      {items.map((item, index) => <fieldset key={item.key} className="rounded-md border border-border-subtle p-4">
        <legend className="px-1 font-semibold">Material {index + 1}</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">Descripción<input aria-label={`Descripción ${index + 1}`} className={inputClass} value={item.description} maxLength={500} required onChange={event => update(item.key, "description", event.target.value)} /></label>
          <label className="text-sm">Unidad de medida<input aria-label={`Unidad ${index + 1}`} className={inputClass} value={item.unit} maxLength={40} placeholder="Ej. saco, m², unidad" required onChange={event => update(item.key, "unit", event.target.value)} /></label>
          <label className="text-sm">Cantidad<input aria-label={`Cantidad ${index + 1}`} className={inputClass} type="number" min="0.001" step="0.001" value={item.quantity} required onChange={event => update(item.key, "quantity", event.target.value)} /></label>
          <label className="text-sm">Precio unitario ({currency})<input aria-label={`Precio unitario ${index + 1}`} className={inputClass} type="number" min="0" step="0.01" value={item.unit_price} required onChange={event => update(item.key, "unit_price", event.target.value)} /></label>
        </div>
        <div className="mt-3 flex items-center justify-between gap-3"><output aria-label={`Subtotal ${index + 1}`}>Subtotal: {subtotal(item)} {currency}</output>
          <button type="button" className="text-sm text-danger underline" onClick={() => { changed(); setItems(items.filter(value => value.key !== item.key)); }} aria-label={`Eliminar material ${index + 1}`}>Eliminar material</button></div>
      </fieldset>)}
      <Button type="button" disabled={items.length >= 200} onClick={() => { changed(); setItems([...items, row(blank())]); }}>Agregar material</Button>
      <p className="text-xl font-bold" aria-live="polite">Total: {total(items)} {currency}</p>
      {dirty && <p className="text-sm text-text-muted">Cambios sin guardar.</p>}
      <div className="flex flex-wrap gap-3"><Button type="submit">{busy ? "Guardando…" : "Guardar cotización"}</Button>
        <Button type="button" onClick={() => void save(true)}>Descargar CSV</Button></div>
      <p className="text-xs text-text-muted">La descarga guarda primero la cotización para tu empresa.</p>
    </fieldset>
    {errors.length > 0 && <ul role="alert" className="text-sm text-danger">{errors.map(error => <li key={error}>{error}</li>)}</ul>}
    {message && <p role="status">{message}</p>}
  </form>;
}
