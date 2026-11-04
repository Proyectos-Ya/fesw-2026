import { defineConfig } from "wxt";

export default defineConfig({
  srcDir: "src",
  manifest: () => ({
    name: "Chiripa — Licitaciones Inteligentes",
    description: "Sincroniza bases oficiales y anexos de Mercado Público para MiPymes.",
    version: "0.1.0",
    permissions: ["storage", "cookies", "alarms"],
    host_permissions: [
      "*://*.mercadopublico.cl/*",
      "*://*.chiripa.cl/*",
      "*://*.proyectosya.cl/*",
      "http://localhost:3000/*",
      "http://localhost:8000/*",
    ],
    optional_host_permissions: [
      "*://mercadopublico.cl/Portal/Modules/Site/Buyer/*",
      "*://proveedor.mercadopublico.cl/*",
    ],
    icons: {
      "16": "icons/icon-16.png",
      "48": "icons/icon-48.png",
      "128": "icons/icon-128.png",
    },
    action: {
      default_title: "Chiripa Licitaciones",
      default_popup: "popup/index.html",
    },
  }),
});
