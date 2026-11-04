import { defineContentScript } from "wxt/sandbox";
import { CHIRIPA_WEB_MATCHES, DEV_WEB_MATCHES } from "../config/web-origins";
import { ContentScriptBridge } from "../services/bridge/content-script-bridge";

const buildMode = (import.meta as ImportMeta & { env?: { MODE?: string } }).env?.MODE;

export default defineContentScript({
  matches: buildMode === "production" ? CHIRIPA_WEB_MATCHES : [...CHIRIPA_WEB_MATCHES, ...DEV_WEB_MATCHES],
  runAt: "document_idle",
  main() {
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
        // En Firefox, los objetos del content script deben clonarse en el scope de la ventana de la página
        const cloneFn = (globalThis as unknown as { cloneInto?: (obj: unknown, target: unknown) => unknown }).cloneInto;
        const payload = typeof cloneFn === "function" ? cloneFn(message, window) : message;
        window.postMessage(payload, targetOrigin);
      },
    });

    window.addEventListener("message", (event) => {
      const data = event.data as Record<string, unknown> | undefined;
      bridge.handleWindowMessage({
        origin: event.origin,
        data: data ?? {},
      });
    });
  },
});
