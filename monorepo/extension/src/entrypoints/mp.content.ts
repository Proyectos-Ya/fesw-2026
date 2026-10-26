import { defineContentScript } from "wxt/sandbox";
import { MpFichaAdapter } from "../adapters/mp/mp-ficha-adapter";

export default defineContentScript({
  matches: ["*://*.mercadopublico.cl/*"],
  runAt: "document_idle",
  async main() {
    const adapter = new MpFichaAdapter(document);
    const hydrated = await adapter.waitForHydration(5000);
    if (!hydrated) return;

    const code = adapter.extractCode();
    if (!code) return;

    const attachments = adapter.extractAttachments();
    if (attachments.length === 0) return;

    // Inyectar un banner discreto en la ficha indicando integración con Chiripa
    const existingBadge = document.getElementById("chiripa-extension-badge");
    if (!existingBadge) {
      const badge = document.createElement("div");
      badge.id = "chiripa-extension-badge";
      badge.style.cssText = `
        position: fixed;
        bottom: 16px;
        right: 16px;
        background: #0f172a;
        color: #f8fafc;
        padding: 8px 14px;
        border-radius: 8px;
        font-family: system-ui, sans-serif;
        font-size: 13px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 999999;
        display: flex;
        align-items: center;
        gap: 8px;
      `;
      badge.innerHTML = `
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#10b981;"></span>
        <span>Chiripa: ${attachments.length} anexo(s) detectado(s)</span>
      `;
      document.body.appendChild(badge);
    }
  },
});
