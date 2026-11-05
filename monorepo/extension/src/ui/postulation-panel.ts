import { PostulationPackagePayload } from "../types/schemas";

export interface PostulationPanelConfig {
  doc?: Document;
  onClearHighlight?: () => void;
  onDownloadAttachments?: () => void;
}

export interface RenderPanelOptions {
  packageData: PostulationPackagePayload;
  filledCount: number;
  incompleteCount: number;
  /** Campos que el usuario debe revisar o completar a mano. */
  pending?: string[];
  /** Aviso cuando no se completó nada (formulario ausente, empresa no verificada…). */
  notice?: string;
  /** Anexo que espera confirmación: Compra Ágil lo sube a su servidor al seleccionarlo. */
  annexToConfirm?: string;
  onConfirmAnnex?: () => void | Promise<void>;
}

const HOST_ID = "chiripa-postulation-panel-host";

export class PostulationPanel {
  private doc: Document;
  private onClearHighlight?: () => void;
  private onDownloadAttachments?: () => void;
  private host: HTMLElement | null = null;
  private shadow: ShadowRoot | null = null;

  constructor(config?: PostulationPanelConfig) {
    this.doc = config?.doc ?? document;
    this.onClearHighlight = config?.onClearHighlight;
    this.onDownloadAttachments = config?.onDownloadAttachments;
  }

  public render(opts: RenderPanelOptions): void {
    this.destroy();

    const host = this.doc.createElement("div");
    host.id = HOST_ID;
    this.doc.body.appendChild(host);

    const shadow = host.attachShadow({ mode: "open" });
    this.host = host;
    this.shadow = shadow;

    // Estilos encapsulados en el Shadow DOM
    const style = this.doc.createElement("style");
    style.textContent = `
      :host {
        all: initial;
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 2147483647;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      .notice {
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid #f59e0b;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 12px;
        margin-bottom: 10px;
      }
      .pending-list {
        margin: 0 0 10px;
        padding-left: 18px;
        font-size: 12px;
        color: #fcd34d;
      }
      .panel {
        width: 320px;
        background: #0f172a;
        color: #f8fafc;
        border-radius: 12px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
        border: 1px solid #1e293b;
        padding: 16px;
        box-sizing: border-box;
      }
      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
      }
      .title {
        font-size: 14px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 8px;
        color: #ffffff;
      }
      .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #10b981;
      }
      .close-btn {
        background: none;
        border: none;
        color: #94a3b8;
        cursor: pointer;
        font-size: 16px;
        padding: 4px;
        border-radius: 4px;
      }
      .close-btn:hover {
        color: #f8fafc;
        background: #334155;
      }
      .tender-info {
        font-size: 12px;
        color: #cbd5e1;
        margin-bottom: 12px;
        background: #1e293b;
        padding: 8px;
        border-radius: 6px;
      }
      .tender-code {
        font-weight: 600;
        color: #38bdf8;
      }
      .metrics {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-bottom: 14px;
      }
      .metric-box {
        background: #1e293b;
        padding: 8px 10px;
        border-radius: 6px;
        text-align: center;
      }
      .metric-num {
        font-size: 18px;
        font-weight: 700;
      }
      .metric-num.green {
        color: #10b981;
      }
      .metric-num.amber {
        color: #f59e0b;
      }
      .metric-label {
        font-size: 11px;
        color: #94a3b8;
        margin-top: 2px;
      }
      .warning-box {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 6px;
        padding: 8px 10px;
        font-size: 11px;
        color: #fde68a;
        margin-bottom: 14px;
        line-height: 1.4;
      }
      .actions {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .btn {
        display: block;
        width: 100%;
        padding: 8px 12px;
        font-size: 12px;
        font-weight: 500;
        border-radius: 6px;
        cursor: pointer;
        text-align: center;
        border: none;
        box-sizing: border-box;
      }
      .btn-outline {
        background: transparent;
        border: 1px solid #475569;
        color: #e2e8f0;
      }
      .btn-outline:hover {
        background: #1e293b;
        border-color: #64748b;
      }
    `;
    shadow.appendChild(style);

    // Contenedor principal
    const panel = this.doc.createElement("div");
    panel.className = "panel";

    // Cabecera
    const header = this.doc.createElement("div");
    header.className = "header";

    const title = this.doc.createElement("div");
    title.className = "title";
    const dot = this.doc.createElement("span");
    dot.className = "dot";
    const titleText = this.doc.createElement("span");
    titleText.textContent = "Chiripa — Postulación Asistida";
    title.appendChild(dot);
    title.appendChild(titleText);

    const closeBtn = this.doc.createElement("button");
    closeBtn.className = "close-btn";
    closeBtn.textContent = "✕";
    closeBtn.setAttribute("aria-label", "Cerrar panel");
    closeBtn.addEventListener("click", () => this.destroy());

    header.appendChild(title);
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Info licitación
    const info = this.doc.createElement("div");
    info.className = "tender-info";
    const codeSpan = this.doc.createElement("span");
    codeSpan.className = "tender-code";
    codeSpan.textContent = opts.packageData.tender_code;
    const companySpan = this.doc.createElement("div");
    companySpan.textContent = `${opts.packageData.company_name} (${opts.packageData.company_rut})`;
    info.appendChild(codeSpan);
    info.appendChild(companySpan);
    panel.appendChild(info);

    // Métricas de campos completados vs pendientes
    const metrics = this.doc.createElement("div");
    metrics.className = "metrics";

    const boxFilled = this.doc.createElement("div");
    boxFilled.className = "metric-box";
    const numFilled = this.doc.createElement("div");
    numFilled.className = "metric-num green";
    numFilled.textContent = String(opts.filledCount);
    const labelFilled = this.doc.createElement("div");
    labelFilled.className = "metric-label";
    labelFilled.textContent = `${opts.filledCount} completados`;
    boxFilled.appendChild(numFilled);
    boxFilled.appendChild(labelFilled);

    const boxInc = this.doc.createElement("div");
    boxInc.className = "metric-box";
    const numInc = this.doc.createElement("div");
    numInc.className = "metric-num amber";
    numInc.textContent = String(opts.incompleteCount);
    const labelInc = this.doc.createElement("div");
    labelInc.className = "metric-label";
    labelInc.textContent = `${opts.incompleteCount} pendientes`;
    boxInc.appendChild(numInc);
    boxInc.appendChild(labelInc);

    metrics.appendChild(boxFilled);
    metrics.appendChild(boxInc);
    panel.appendChild(metrics);

    if (opts.notice) {
      const notice = this.doc.createElement("div");
      notice.className = "notice";
      notice.textContent = opts.notice;
      panel.appendChild(notice);
    }

    if (opts.pending && opts.pending.length > 0) {
      const list = this.doc.createElement("ul");
      list.className = "pending-list";
      for (const label of opts.pending) {
        const li = this.doc.createElement("li");
        li.textContent = label;
        list.appendChild(li);
      }
      panel.appendChild(list);
    }

    if (opts.annexToConfirm && opts.onConfirmAnnex) {
      const annexBox = this.doc.createElement("div");
      annexBox.className = "notice";
      annexBox.textContent = `Borrador listo: ${opts.annexToConfirm}. El archivo se sube a Mercado Público apenas lo adjuntamos, aunque aún no envíes la cotización.`;
      const confirmBtn = this.doc.createElement("button");
      confirmBtn.id = "btnChiripaConfirmAnnex";
      confirmBtn.className = "btn btn-outline";
      confirmBtn.textContent = "Subir borrador de postulación";
      const onConfirm = opts.onConfirmAnnex;
      confirmBtn.addEventListener("click", () => {
        confirmBtn.disabled = true;
        void onConfirm();
      });
      annexBox.appendChild(confirmBtn);
      panel.appendChild(annexBox);
    }

    // Aviso de seguridad y manual submission (CA8)
    const warning = this.doc.createElement("div");
    warning.className = "warning-box";
    warning.textContent =
      "⚠️ Recuerda revisar cada campo y enviar la oferta manualmente en Mercado Público. Chiripa nunca enviará la postulación por ti.";
    panel.appendChild(warning);

    // Botones de acción
    const actions = this.doc.createElement("div");
    actions.className = "actions";

    const clearBtn = this.doc.createElement("button");
    clearBtn.id = "btnChiripaClearHighlight";
    clearBtn.className = "btn btn-outline";
    clearBtn.textContent = "Quitar resaltado de campos";
    clearBtn.addEventListener("click", () => {
      if (this.onClearHighlight) {
        this.onClearHighlight();
      }
    });
    actions.appendChild(clearBtn);

    if (opts.packageData.files.length > 0 && this.onDownloadAttachments) {
      const downloadBtn = this.doc.createElement("button");
      downloadBtn.className = "btn btn-outline";
      downloadBtn.textContent = `Descargar ${opts.packageData.files.length} archivo(s)`;
      downloadBtn.addEventListener("click", () => {
        this.onDownloadAttachments?.();
      });
      actions.appendChild(downloadBtn);
    }

    panel.appendChild(actions);
    shadow.appendChild(panel);

    // Inyectar hoja de estilos global en el documento para colorear campos marcados (CA7)
    this.injectHighlightStyles();
  }

  private injectHighlightStyles(): void {
    const styleId = "chiripa-highlight-styles";
    if (!this.doc.getElementById(styleId)) {
      const style = this.doc.createElement("style");
      style.id = styleId;
      style.textContent = `
        [data-chiripa-field-status="filled"] {
          border: 2px solid #10b981 !important;
          background-color: rgba(16, 185, 129, 0.08) !important;
          transition: all 0.2s ease-in-out;
        }
        [data-chiripa-field-status="incomplete"] {
          border: 2px solid #f59e0b !important;
          background-color: rgba(245, 158, 11, 0.08) !important;
          transition: all 0.2s ease-in-out;
        }
      `;
      this.doc.head.appendChild(style);
    }
  }

  public destroy(): void {
    if (this.host && this.host.parentNode) {
      this.host.parentNode.removeChild(this.host);
    }
    this.host = null;
    this.shadow = null;

    const highlightStyle = this.doc.getElementById("chiripa-highlight-styles");
    if (highlightStyle && highlightStyle.parentNode) {
      highlightStyle.parentNode.removeChild(highlightStyle);
    }
  }
}
