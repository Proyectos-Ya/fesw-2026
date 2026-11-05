import { defineContentScript } from "wxt/sandbox";
import { CompraAgilAdapter, parseCompraAgilCode } from "../adapters/mp/compra-agil-adapter";
import { waitForSessionRut } from "../adapters/mp/compra-agil-session";
import { MpFichaAdapter } from "../adapters/mp/mp-ficha-adapter";
import { MpPostulationAdapter } from "../adapters/mp/mp-postulation-adapter";
import { PostulationPackagePayload } from "../types/schemas";
import { runCompraAgilFlow } from "../services/postulation/compra-agil-flow";
import { PostulationPanel } from "../ui/postulation-panel";

const requestPendingPackage = (tenderCode: string) =>
  new Promise<PostulationPackagePayload | null>((resolve) => {
    chrome.runtime.sendMessage({ action: "GET_PENDING_POSTULATION", tender_code: tenderCode }, (r) =>
      resolve((r as { packageData?: PostulationPackagePayload | null } | undefined)?.packageData ?? null)
    );
  });

/** Compra Ágil (SPA): espera el formulario y aplica el paquete pendiente. */
function startCompraAgil(): void {
  const adapter = new CompraAgilAdapter(document);
  let panel: PostulationPanel | null = null;
  let running = false;

  const apply = async () => {
    const tenderCode = parseCompraAgilCode(window.location.href);
    if (!tenderCode || running) return;
    running = true;
    try {
      await runCompraAgilFlow({
        tenderCode,
        getPackage: requestPendingPackage,
        waitForForm: () => adapter.waitForForm(30_000),
        getSessionRut: () => waitForSessionRut(),
        fill: (pkg, options) => adapter.fill(pkg, options),
        attachAnnex: (files) => adapter.attachAnnex(files),
        render: (state) => {
          panel ??= new PostulationPanel({ doc: document, onClearHighlight: () => adapter.clearHighlighting() });
          panel.render(state);
        },
      });
    } catch (e) {
      console.error("[Chiripa] Error aplicando el paquete en Compra Ágil:", e);
    } finally {
      running = false;
    }
  };

  void apply();

  // El usuario confirma en Chiripa con la pestaña ya abierta
  chrome.runtime.onMessage.addListener((message) => {
    if (message?.action === "PACKAGE_READY" && message?.tender_code === parseCompraAgilCode(window.location.href)) {
      void apply();
    }
  });

  // La SPA navega con History API: reintentar al llegar a otra cotización
  let lastHref = window.location.href;
  setInterval(() => {
    if (window.location.href !== lastHref) {
      lastHref = window.location.href;
      void apply();
    }
  }, 1000);
}

export default defineContentScript({
  matches: ["*://*.mercadopublico.cl/*"],
  runAt: "document_idle",
  async main() {
    if (window.location.hostname === "compra-agil.mercadopublico.cl") {
      startCompraAgil();
      return;
    }

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
        background: #FFFFFF;
        color: #2A2620;
        border: 1px solid #E8E1D5;
        padding: 8px 14px;
        border-radius: 12px;
        font-family: "Hanken Grotesk", system-ui, -apple-system, "Segoe UI", sans-serif;
        font-size: 13px;
        font-weight: 600;
        box-shadow: 0 12px 32px rgba(27, 24, 20, 0.10), 0 3px 8px rgba(27, 24, 20, 0.05);
        z-index: 999999;
        display: flex;
        align-items: center;
        gap: 8px;
      `;
      const dot = document.createElement("span");
      dot.style.cssText =
        "display:inline-block;width:8px;height:8px;border-radius:50%;background:#6D8657;box-shadow:0 0 0 3px #F1F5EB;";

      const text = document.createElement("span");
      text.textContent = `Chiripa: ${attachments.length} anexo(s) detectado(s)`;

      badge.appendChild(dot);
      badge.appendChild(text);
      document.body.appendChild(badge);
    }
  },
});
