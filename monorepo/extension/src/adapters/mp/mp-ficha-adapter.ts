import { MpDocumentItem } from "../../types/schemas";

export class MpFichaAdapter {
  private document: Document;

  constructor(doc: Document = typeof document !== "undefined" ? document : ({} as Document)) {
    this.document = doc;
  }

  public extractCode(searchParams?: string): string | null {
    // 1. Desde query param ?code=
    const search = searchParams !== undefined ? searchParams : (typeof window !== "undefined" ? window.location.search : "");
    const params = new URLSearchParams(search);
    const codeParam = params.get("code");
    if (codeParam) return codeParam.trim();

    // 2. Fallback a encabezados de la ficha
    if (this.document.querySelector) {
      const codeEl = this.document.querySelector(
        '[data-testid="tender-code"], .codigo-licitacion, h1, h2'
      );
      if (codeEl?.textContent) {
        const match = codeEl.textContent.match(/\d+-\d+-(?:COT|L1|LE|LP)\d+/i);
        if (match) return match[0].toUpperCase();
      }
    }
    return null;
  }

  public extractCallInfo(): {
    call_number: 1 | 2;
    first_call: string | null;
    second_call: string | null;
  } {
    const bodyText = (this.document.body && (this.document.body.innerText || this.document.body.textContent)) || "";
    const isSecondCall = /segundo\s+llamado|2[°º.]?\s*llamado/i.test(bodyText);

    return {
      call_number: isSecondCall ? 2 : 1,
      first_call: this.extractDateByLabel(["Cierre primer llamado", "Fecha de cierre"]),
      second_call: isSecondCall ? this.extractDateByLabel(["Cierre segundo llamado", "Nuevo cierre"]) : null,
    };
  }

  public extractAttachments(): MpDocumentItem[] {
    const documents: MpDocumentItem[] = [];
    if (!this.document.querySelectorAll) return documents;

    const rows = this.document.querySelectorAll(
      'table[data-section="adjuntos"] tbody tr, .tabla-adjuntos tbody tr, tr[ng-repeat*="adjunto"], tr.attachment-row'
    );

    rows.forEach((row, idx) => {
      const nameEl = row.querySelector(
        '.nombre-archivo, td[data-col="nombre"], a.download-link, td:nth-child(1)'
      );
      const name = nameEl?.textContent?.trim();
      if (!name) return;

      const idAttr =
        row.getAttribute("data-id") ||
        row.querySelector("[data-doc-id]")?.getAttribute("data-doc-id");
      const mp_document_id = idAttr || `mp-doc-${idx + 1}`;

      documents.push({
        mp_document_id,
        name,
      });
    });

    return documents;
  }

  public extractDateByLabel(labels: string[]): string | null {
    const bodyText = (this.document.body && (this.document.body.innerText || this.document.body.textContent)) || "";
    for (const label of labels) {
      const regex = new RegExp(
        `${label}[:\\s]+([0-9]{2}[/-][0-9]{2}[/-][0-9]{4}(?:\\s+[0-9]{2}:[0-9]{2})?)`,
        "i"
      );
      const match = bodyText.match(regex);
      if (match) return match[1];
    }
    return null;
  }

  public async waitForHydration(timeoutMs: number = 10000): Promise<boolean> {
    const startTime = Date.now();
    return new Promise((resolve) => {
      const check = () => {
        const hasCode = Boolean(this.extractCode());
        const hasDocs =
          this.extractAttachments().length > 0 ||
          Boolean(this.document.querySelector && this.document.querySelector(".sin-adjuntos"));

        if (hasCode && hasDocs) {
          resolve(true);
          return;
        }
        if (Date.now() - startTime > timeoutMs) {
          resolve(false);
          return;
        }
        setTimeout(check, 250);
      };
      check();
    });
  }
}
