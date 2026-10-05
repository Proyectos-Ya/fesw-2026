import { defineContentScript } from "wxt/sandbox";
import { ContentScriptBridge } from "../services/bridge/content-script-bridge";

export default defineContentScript({
  matches: [
    "*://*.chiripa.cl/*",
    "*://*.proyectosya.cl/*",
    "http://localhost:3000/*",
  ],
  runAt: "document_idle",
  main() {
    const bridge = new ContentScriptBridge({
      currentOrigin: window.location.origin,
      extensionVersion: "0.1.0",
      sendMessageToRuntime: (message, cb) => {
        if (cb) {
          chrome.runtime.sendMessage(message, cb);
        } else {
          chrome.runtime.sendMessage(message);
        }
      },
      postMessageToWindow: (message, targetOrigin) => window.postMessage(message, targetOrigin),
    });

    window.addEventListener("message", (event) => {
      bridge.handleWindowMessage({
        origin: event.origin,
        data: event.data as Record<string, unknown>,
      });
    });
  },
});
