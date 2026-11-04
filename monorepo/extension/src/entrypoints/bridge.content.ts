import { defineContentScript } from "wxt/sandbox";
import { ContentScriptBridge } from "../services/bridge/content-script-bridge";

export default defineContentScript({
  matches: [
    "*://*.chiripa.cl/*",
    "*://*.proyectosya.cl/*",
    "*://*.vercel.app/*",
    "http://localhost/*",
    "http://127.0.0.1/*",
  ],
  runAt: "document_idle",
  main() {
    console.log("[Chiripa Extension] Content script bridge cargado en:", window.location.href);
    const bridge = new ContentScriptBridge({
      currentOrigin: window.location.origin,
      extensionVersion: chrome.runtime?.getManifest?.()?.version ?? "0.2.0",
      sendMessageToRuntime: (message, cb) => {
        if (cb) {
          chrome.runtime.sendMessage(message, cb);
        } else {
          chrome.runtime.sendMessage(message);
        }
      },
      postMessageToWindow: (message, targetOrigin) => {
        try {
          // En Firefox, los objetos del content script deben clonarse en el scope de la ventana de la página
          const cloneFn = (globalThis as unknown as { cloneInto?: (obj: unknown, target: unknown) => unknown }).cloneInto;
          const payload = typeof cloneFn === "function" ? cloneFn(message, window) : message;
          window.postMessage(payload, targetOrigin || "*");
        } catch (err) {
          console.warn("[Chiripa Extension] Error en cloneInto/postMessage, reintentando directo:", err);
          window.postMessage(message, targetOrigin || "*");
        }
      },
    });

    window.addEventListener("message", (event) => {
      const data = event.data as Record<string, unknown> | undefined;
      if (data?.target === "CHIRIPA_EXTENSION") {
        console.log("[Chiripa Extension] Mensaje recibido en bridge:", data.type, "origin:", event.origin);
      }
      bridge.handleWindowMessage({
        origin: event.origin,
        data: data ?? {},
      });
    });
  },
});
