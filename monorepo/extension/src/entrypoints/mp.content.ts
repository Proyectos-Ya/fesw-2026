import { defineContentScript } from "wxt/sandbox";
import { MpFichaAdapter } from "../adapters/mp/mp-ficha-adapter";
import { MpPostulationAdapter } from "../adapters/mp/mp-postulation-adapter";
import { PostulationPackagePayload } from "../types/schemas";
import { PostulationPanel } from "../ui/postulation-panel";

export default defineContentScript({
  matches: ["*://*.mercadopublico.cl/*"],
  allFrames: true,
  runAt: "document_idle",
  async main() {
    const postulationAdapter = new MpPostulationAdapter(document);
    const state = postulationAdapter.detectState();

    // CA5: Si está en login, detección pasiva sin tocar credenciales ni inputs
    if (state.isLogin) {
      // No hacemos nada con inputs ni contraseñas.
      return;
    }

    // CA6, CA7, CA8: Si está en el formulario de postulación
    if (state.isForm && state.tenderCode) {
      let panel: PostulationPanel | null = null;

      const loadAndApplyPackage = async () => {
        try {
          const resp = await new Promise<{ packageData?: PostulationPackagePayload | null }>(
            (resolve) => {
              chrome.runtime.sendMessage(
                { action: "GET_PENDING_POSTULATION", tender_code: state.tenderCode },
                (r) => resolve(r ?? {})
              );
            }
          );

          if (resp?.packageData) {
            const fillRes = postulationAdapter.fillPostulation(resp.packageData);
            if (fillRes.success) {
              if (!panel) {
                panel = new PostulationPanel({
                  doc: document,
                  onClearHighlight: () => postulationAdapter.clearHighlighting(),
                });
              }
              panel.render({
                packageData: resp.packageData,
                filledCount: fillRes.filledCount,
                incompleteCount: fillRes.incompleteCount,
              });
            }
          }
        } catch (e) {
          console.error("[MP Postulation] Error cargando paquete:", e);
        }
      };

      // Intentar aplicar inmediatamente si ya hay paquete confirmado
      await loadAndApplyPackage();

      // Escuchar si el usuario confirma la postulación desde Chiripa mientras la pestaña está abierta
      chrome.runtime.onMessage.addListener((message) => {
        if (message?.action === "PACKAGE_READY" && message?.tender_code === state.tenderCode) {
          loadAndApplyPackage();
        }
      });

      return;
    }

    // Flujo complementario: Ficha informativa de licitación (anexos detectados)
    const fichaAdapter = new MpFichaAdapter(document);
    const hydrated = await fichaAdapter.waitForHydration(5000);
    if (!hydrated) return;

    const code = fichaAdapter.extractCode();
    if (!code) return;

    const attachments = fichaAdapter.extractAttachments();
    if (attachments.length === 0) return;

    // Inyectar un badge discreto en la ficha indicando integración con Chiripa
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
      const dot = document.createElement("span");
      dot.style.cssText =
        "display:inline-block;width:8px;height:8px;border-radius:50%;background:#10b981;";

      const text = document.createElement("span");
      text.textContent = `Chiripa: ${attachments.length} anexo(s) detectado(s)`;

      badge.appendChild(dot);
      badge.appendChild(text);
      document.body.appendChild(badge);
    }
  },
});
