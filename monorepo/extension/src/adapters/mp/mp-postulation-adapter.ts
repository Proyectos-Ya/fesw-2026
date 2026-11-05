import { PostulationPackagePayload } from "../../types/schemas";

export interface PostulationFillResult {
  success: boolean;
  filledCount: number;
  incompleteCount: number;
  error?: "RUT_MISMATCH" | "TENDER_CODE_MISMATCH" | "FORM_NOT_FOUND" | string;
}

export interface AdapterPageStatus {
  isLogin: boolean;
  isForm: boolean;
  canPostulate: boolean;
  tenderCode: string | null;
  sessionRut: string | null;
}

export class MpPostulationAdapter {
  private doc: Document;

  constructor(doc: Document = document) {
    this.doc = doc;
  }

  /**
   * CA5: Detecta si la página actual es la pantalla de inicio de sesión de Mercado Público.
   * En ningún momento interactúa con inputs ni lee contraseñas.
   */
  public isLoginPage(): boolean {
    const hasLoginAction =
      Boolean(this.doc.querySelector("form[action*='Login']")) ||
      Boolean(this.doc.querySelector("form[action*='login']")) ||
      Boolean(this.doc.querySelector("#lnkClaveUnica"));

    const hasUserField = Boolean(this.doc.querySelector("#txtUsuario"));
    return hasLoginAction && hasUserField;
  }

  /**
   * Detecta si la página actual corresponde a un formulario de oferta / postulación en MP.
   */
  public isPostulationForm(): boolean {
    const hasFormOrTable =
      Boolean(this.doc.querySelector("#tblItems")) ||
      Boolean(this.doc.querySelector("#formPostulacion")) ||
      Boolean(this.doc.querySelector(".table-items")) ||
      Boolean(this.doc.querySelector("input[name*='precio' i]"));

    return hasFormOrTable;
  }

  /**
   * Extrae el código de licitación del encabezado o ficha.
   */
  public extractTenderCode(): string | null {
    const el =
      this.doc.getElementById("lblNumeroLicitacion") ??
      this.doc.querySelector(".tender-header span") ??
      this.doc.querySelector("[data-tender-code]");

    if (el?.textContent) {
      const match = el.textContent.match(/\d+-\d+-[a-zA-Z0-9]+/);
      if (match) return match[0];
      return el.textContent.trim();
    }
    return null;
  }

  /**
   * Extrae el RUT del usuario autenticado en la sesión actual de MP.
   */
  public extractSessionRut(): string | null {
    const rutEl =
      this.doc.getElementById("lblUsuarioRUT") ??
      this.doc.querySelector(".user-session #lblUsuarioRUT") ??
      this.doc.querySelector("[data-user-rut]");

    if (rutEl?.textContent) {
      const cleaned = rutEl.textContent.trim();
      return cleaned;
    }
    return null;
  }

  public detectState(): AdapterPageStatus {
    const isLogin = this.isLoginPage();
    const isForm = this.isPostulationForm();
    const tenderCode = this.extractTenderCode();
    const sessionRut = this.extractSessionRut();

    return {
      isLogin,
      isForm,
      canPostulate: isForm && !isLogin,
      tenderCode,
      sessionRut,
    };
  }

  /**
   * CA6 & CA7: Autocompleta los datos del formulario respetando la sesión y resalta campos.
   * CA8: Garantiza 0 invocaciones a envío.
   */
  public fillPostulation(packageData: PostulationPackagePayload): PostulationFillResult {
    if (!this.isPostulationForm()) {
      return { success: false, filledCount: 0, incompleteCount: 0, error: "FORM_NOT_FOUND" };
    }

    const currentTenderCode = this.extractTenderCode();
    if (currentTenderCode && currentTenderCode !== packageData.tender_code) {
      return {
        success: false,
        filledCount: 0,
        incompleteCount: 0,
        error: "TENDER_CODE_MISMATCH",
      };
    }

    // CA6: Validación estricta de RUT de sesión vs empresa
    const sessionRut = this.extractSessionRut();
    if (sessionRut) {
      const normSession = sessionRut.replace(/\./g, "").toUpperCase();
      const normCompany = packageData.company_rut.replace(/\./g, "").toUpperCase();
      if (normSession !== normCompany) {
        return {
          success: false,
          filledCount: 0,
          incompleteCount: 0,
          error: "RUT_MISMATCH",
        };
      }
    }

    let filledCount = 0;
    let incompleteCount = 0;

    // 1. Llenar ítems de la cotización
    // Buscar filas de la tabla de items
    const rows = Array.from(this.doc.querySelectorAll("#tblItems tbody tr, tr[data-line]"));
    if (rows.length > 0) {
      rows.forEach((row, idx) => {
        const lineAttr = row.getAttribute("data-line");
        const lineNumber = lineAttr ? parseInt(lineAttr, 10) : idx + 1;

        const matchedItem = packageData.items.find((it) => it.line_number === lineNumber);
        const inputPrecio =
          (row.querySelector("input[name*='precio' i]") as HTMLInputElement | null) ??
          (row.querySelector(`#txtPrecioUnitario_${idx}`) as HTMLInputElement | null);

        if (inputPrecio) {
          if (matchedItem) {
            inputPrecio.value = String(matchedItem.unit_price);
            this.dispatchChange(inputPrecio);
            this.markFieldStatus(inputPrecio, "filled");
            filledCount++;
          } else {
            this.markFieldStatus(inputPrecio, "incomplete");
            incompleteCount++;
          }
        }
      });
    }

    // 2. Llenar observaciones (respetando tope de 255 caracteres si aplica)
    const obsEl =
      (this.doc.getElementById("txtObservaciones") as HTMLTextAreaElement | null) ??
      (this.doc.querySelector("textarea[name*='observaciones' i]") as HTMLTextAreaElement | null);

    if (obsEl && packageData.observations) {
      const maxLen = obsEl.maxLength > 0 ? obsEl.maxLength : 255;
      obsEl.value = packageData.observations.slice(0, maxLen);
      this.dispatchChange(obsEl);
      this.markFieldStatus(obsEl, "filled");
      filledCount++;
    } else if (obsEl) {
      this.markFieldStatus(obsEl, "incomplete");
      incompleteCount++;
    }

    // 3. Llenar plazo de entrega y validez de oferta
    const plazoEl =
      (this.doc.getElementById("txtPlazoEntrega") as HTMLInputElement | null) ??
      (this.doc.querySelector("input[name*='plazo' i]") as HTMLInputElement | null);

    if (plazoEl && packageData.delivery_term_days) {
      plazoEl.value = String(packageData.delivery_term_days);
      this.dispatchChange(plazoEl);
      this.markFieldStatus(plazoEl, "filled");
      filledCount++;
    }

    const validezEl =
      (this.doc.getElementById("txtValidezOferta") as HTMLInputElement | null) ??
      (this.doc.querySelector("input[name*='validez' i]") as HTMLInputElement | null);

    if (validezEl && packageData.validity_days) {
      validezEl.value = String(packageData.validity_days);
      this.dispatchChange(validezEl);
      this.markFieldStatus(validezEl, "filled");
      filledCount++;
    }

    return {
      success: true,
      filledCount,
      incompleteCount,
    };
  }

  /**
   * CA7: Limpia atributos y marcas de resaltado
   */
  public clearHighlighting(): void {
    const els = this.doc.querySelectorAll("[data-chiripa-field-status]");
    els.forEach((el) => el.removeAttribute("data-chiripa-field-status"));
  }

  private markFieldStatus(el: HTMLElement, status: "filled" | "incomplete"): void {
    el.setAttribute("data-chiripa-field-status", status);
  }

  private dispatchChange(el: HTMLElement): void {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }
}
