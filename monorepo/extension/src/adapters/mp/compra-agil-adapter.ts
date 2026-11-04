import {
  PostulationFileAttachment,
  PostulationItemPayload,
  PostulationPackagePayload,
} from "../../types/schemas";
import { COMPRA_AGIL } from "./compra-agil-selectors";

export interface CompraAgilFillResult {
  success: boolean;
  filledCount: number;
  incompleteCount: number;
  /** Nombres visibles de los campos que el usuario debe revisar o completar a mano. */
  pending: string[];
  /** Anexo listo para subir; Compra Ágil lo sube al servidor al seleccionarlo, así que espera confirmación. */
  annexReady?: string;
  error?: "TENDER_CODE_MISMATCH" | "IDENTITY_UNVERIFIED" | "RUT_MISMATCH" | "FORM_NOT_FOUND";
}

type TextControl = HTMLInputElement | HTMLTextAreaElement;

interface ItemBlock {
  productId: string;
  name: string;
  input: HTMLInputElement;
}

interface PendingWrite {
  el: TextControl;
  expected: string;
  label: string;
  matches: (value: string) => boolean;
}

/** Código de la cotización si la URL es la ficha de Compra Ágil; si no, null. */
export function parseCompraAgilCode(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.hostname !== COMPRA_AGIL.host) return null;
    const match = parsed.pathname.match(COMPRA_AGIL.pathPattern);
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

export function normalizeRut(rut: string): string {
  return rut.replace(/[^0-9kK]/g, "").toUpperCase();
}

const onlyDigits = (value: string) => value.replace(/\D/g, "");
const ownText = (el: Element) => el.textContent?.trim() ?? "";
const pad = (n: number) => String(n).padStart(2, "0");

/** Fecha local dentro de `days` días, en el formato del datepicker de MP (dd/mm/aaaa). */
export function validityDate(days: number, now: Date = new Date()): string {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + days);
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}

function toFile(attachment: PostulationFileAttachment): File {
  const binary = atob(attachment.data_base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new File([bytes], attachment.name, { type: attachment.type });
}

const nextTick = () => new Promise<void>((resolve) => setTimeout(resolve, 30));

/**
 * Adaptador del formulario «Participar de la Compra Ágil» (SPA React).
 * Escribe con el setter nativo para que React registre el cambio y solo marca un campo
 * como completado si el valor sigue ahí tras el re-render. Nunca pulsa botones (CA8).
 */
export class CompraAgilAdapter {
  private doc: Document;

  constructor(doc: Document = document) {
    this.doc = doc;
  }

  public headerCode(): string | null {
    for (const h of Array.from(this.doc.querySelectorAll("h1, h2"))) {
      const match = ownText(h).match(COMPRA_AGIL.headerPattern);
      if (match) return match[1];
    }
    return null;
  }

  public isFormReady(): boolean {
    const hasHeading = Array.from(this.doc.querySelectorAll("h2, h3, h4")).some(
      (h) => ownText(h) === COMPRA_AGIL.participarHeading
    );
    return hasHeading && this.findItemBlocks().length > 0;
  }

  /** Espera a que la SPA renderice el formulario, con un plazo máximo. */
  public waitForForm(timeoutMs = 30_000): Promise<boolean> {
    if (this.isFormReady()) return Promise.resolve(true);
    return new Promise((resolve) => {
      const target = this.doc.body ?? this.doc.documentElement;
      const observer = new MutationObserver(() => {
        if (this.isFormReady()) finish(true);
      });
      const timer = setTimeout(() => finish(false), timeoutMs);
      const finish = (ready: boolean) => {
        observer.disconnect();
        clearTimeout(timer);
        resolve(ready);
      };
      observer.observe(target, { childList: true, subtree: true });
    });
  }

  public async fill(
    pkg: PostulationPackagePayload,
    options: { sessionRut: string | null }
  ): Promise<CompraAgilFillResult> {
    const fail = (error: CompraAgilFillResult["error"]): CompraAgilFillResult => ({
      success: false,
      filledCount: 0,
      incompleteCount: 0,
      pending: [],
      error,
    });

    if (!this.isFormReady()) return fail("FORM_NOT_FOUND");
    if (this.headerCode() !== pkg.tender_code) return fail("TENDER_CODE_MISMATCH");
    if (!options.sessionRut) return fail("IDENTITY_UNVERIFIED");
    if (normalizeRut(options.sessionRut) !== normalizeRut(pkg.company_rut)) return fail("RUT_MISMATCH");

    const writes: PendingWrite[] = [];
    const pending: string[] = [];

    const blocks = this.findItemBlocks();
    blocks.forEach((block, idx) => {
      const item = this.matchItem(block, idx, blocks, pkg.items);
      if (!item) {
        this.mark(block.input, "incomplete");
        pending.push(block.name);
        return;
      }
      const expected = String(Math.round(item.unit_price));
      writes.push({
        el: block.input,
        expected,
        label: block.name,
        matches: (value) => onlyDigits(value) === expected,
      });
    });

    const detail = this.controlNear(COMPRA_AGIL.labels.detail);
    if (detail && pkg.observations) {
      const maxLength = detail.maxLength > 0 ? detail.maxLength : COMPRA_AGIL.detailMaxLength;
      const expected = pkg.observations.slice(0, maxLength);
      writes.push({
        el: detail,
        expected,
        label: COMPRA_AGIL.labels.detail,
        matches: (value) => value === expected,
      });
    } else if (detail) {
      this.mark(detail, "incomplete");
      pending.push(COMPRA_AGIL.labels.detail);
    }

    // El paquete aún no trae el valor de despacho: queda para el usuario.
    const shipping = this.controlNear(COMPRA_AGIL.labels.shipping);
    if (shipping) {
      this.mark(shipping, "incomplete");
      pending.push(COMPRA_AGIL.labels.shipping);
    }

    const validity = this.controlNear(COMPRA_AGIL.labels.validity);
    if (validity) {
      const expected = validityDate(pkg.validity_days);
      writes.push({
        el: validity,
        expected,
        label: COMPRA_AGIL.labels.validity,
        matches: (value) => value === expected,
      });
    }

    for (const write of writes) {
      this.setNativeValue(write.el, write.expected);
    }

    await nextTick();

    let filledCount = 0;
    for (const write of writes) {
      if (write.matches(write.el.value)) {
        this.mark(write.el, "filled");
        filledCount++;
      } else {
        this.mark(write.el, "incomplete");
        pending.push(write.label);
      }
    }

    // Los anexos no se tocan hasta que el usuario confirme en el panel (ver attachAnnex).
    const annexReady = this.pickAnnex(pkg.files);
    pending.push(...pkg.files.map((f) => f.name));

    return {
      success: true,
      filledCount,
      incompleteCount: pending.length,
      pending,
      ...(annexReady ? { annexReady: annexReady.name } : {}),
    };
  }

  /**
   * Adjunta el primer archivo aceptado por Compra Ágil (un solo «documento anexo»).
   * Solo debe llamarse tras la confirmación del usuario: Mercado Público sube el
   * archivo a su servidor apenas se selecciona. Los demás quedan pendientes.
   */
  public async attachAnnex(
    files: PostulationFileAttachment[]
  ): Promise<{ attached: string | null; pending: string[] }> {
    const input = this.annexInput();
    const chosen = input ? this.pickAnnex(files) : null;
    const pending = files.filter((f) => f !== chosen).map((f) => f.name);
    if (!input || !chosen) return { attached: null, pending };

    const transfer = new DataTransfer();
    transfer.items.add(toFile(chosen));
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await nextTick();

    const attached = input.files?.[0]?.name === chosen.name;
    this.mark(input, attached ? "filled" : "incomplete");
    return attached ? { attached: chosen.name, pending } : { attached: null, pending: [chosen.name, ...pending] };
  }

  private pickAnnex(files: PostulationFileAttachment[]): PostulationFileAttachment | null {
    return (
      files.find(
        (f) =>
          f.size <= COMPRA_AGIL.annexMaxBytes &&
          COMPRA_AGIL.annexExtensions.some((ext) => f.name.toLowerCase().endsWith(ext))
      ) ?? null
    );
  }

  private annexInput(): HTMLInputElement | null {
    const label = this.findLabels(this.doc, COMPRA_AGIL.labels.annex)[0];
    for (let a = label?.parentElement ?? null, depth = 0; a && depth < 4; depth++, a = a.parentElement) {
      const input = a.querySelector<HTMLInputElement>("input[type='file']");
      if (input) return input;
    }
    return null;
  }

  public clearHighlighting(): void {
    this.doc
      .querySelectorAll("[data-chiripa-field-status]")
      .forEach((el) => el.removeAttribute("data-chiripa-field-status"));
  }

  private findItemBlocks(): ItemBlock[] {
    const idElements = Array.from(this.doc.querySelectorAll("p, span, div")).filter(
      (el) => el.children.length === 0 && COMPRA_AGIL.productIdPattern.test(ownText(el))
    );

    const blocks: ItemBlock[] = [];
    for (const idEl of idElements) {
      let ancestor = idEl.parentElement;
      for (let depth = 0; ancestor && depth < 6; depth++, ancestor = ancestor.parentElement) {
        const label = this.findLabels(ancestor, COMPRA_AGIL.labels.unitPrice)[0];
        if (!label) continue;
        const idsInside = idElements.filter((other) => ancestor!.contains(other)).length;
        const input = this.controlFromLabel(label, ancestor);
        if (idsInside === 1 && input instanceof HTMLInputElement) {
          const productId = ownText(idEl).match(COMPRA_AGIL.productIdPattern)![1];
          const name = ownText(idEl.previousElementSibling ?? idEl) || `ID ${productId}`;
          blocks.push({ productId, name, input });
        }
        break;
      }
    }
    return blocks;
  }

  private matchItem(
    block: ItemBlock,
    idx: number,
    blocks: ItemBlock[],
    items: PostulationItemPayload[]
  ): PostulationItemPayload | null {
    const sameIdOnPage = blocks.filter((b) => b.productId === block.productId).length;
    const byCode = items.filter((it) => it.product_code === block.productId);
    if (sameIdOnPage === 1 && byCode.length === 1) return byCode[0];

    if (items.length === blocks.length) {
      const byOrder = items[idx];
      if (!byOrder.product_code || byOrder.product_code === block.productId) return byOrder;
    }
    return null;
  }

  private findLabels(root: ParentNode, text: string): Element[] {
    return Array.from(root.querySelectorAll("label, span, p, div, legend")).filter(
      (el) => ownText(el) === text && !Array.from(el.children).some((c) => ownText(c) === text)
    );
  }

  private controlNear(labelText: string): TextControl | null {
    const label = this.findLabels(this.doc, labelText)[0];
    return label ? this.controlFromLabel(label, null) : null;
  }

  /** Primer control editable en los ancestros cercanos de la etiqueta, sin salir de `limit`. */
  private controlFromLabel(label: Element, limit: Element | null): TextControl | null {
    let ancestor = label.parentElement;
    for (let depth = 0; ancestor && depth < 4; depth++, ancestor = ancestor.parentElement) {
      const control = ancestor.querySelector<TextControl>(
        "input[type='text']:not([disabled]):not([readonly]), input:not([type]):not([disabled]):not([readonly]), textarea:not([disabled]):not([readonly]):not([aria-hidden='true'])"
      );
      if (control) return control;
      if (ancestor === limit) break;
    }
    return null;
  }

  private setNativeValue(el: TextControl, value: string): void {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    if (setter) {
      setter.call(el, value);
    } else {
      el.value = value;
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  private mark(el: HTMLElement, status: "filled" | "incomplete"): void {
    el.setAttribute("data-chiripa-field-status", status);
  }
}
