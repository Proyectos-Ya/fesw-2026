import pkg from "../../package.json";

export interface ManifestOptions {
  mode?: string;
  browser?: string;
  version?: string;
  origins?: string[];
}

export function buildManifest(options: ManifestOptions = {}) {
  const isDevOrE2E = options.mode === "development" || options.mode === "e2e";
  const isFirefox = options.browser === "firefox";
  const version = options.version ?? pkg.version ?? "0.2.0";

  const hostPermissions: string[] = [
    "*://*.mercadopublico.cl/*",
    "*://*.chiripa.cl/*",
    "*://*.proyectosya.cl/*",
    "*://*.vercel.app/*",
  ];

  if (options.origins) {
    for (const origin of options.origins) {
      if (!hostPermissions.includes(origin)) {
        hostPermissions.push(origin);
      }
    }
  }

  if (isDevOrE2E) {
    hostPermissions.push("http://localhost/*");
    hostPermissions.push("http://127.0.0.1/*");
    hostPermissions.push("http://localhost:3000/*");
    hostPermissions.push("http://127.0.0.1:3000/*");
    hostPermissions.push("http://localhost:8000/*");
    hostPermissions.push("http://127.0.0.1:8000/*");
  }

  const baseManifest: Record<string, unknown> = {
    name: "Chiripa — Licitaciones Inteligentes",
    description: "Sincroniza bases oficiales y asiste la postulación en Mercado Público para MiPymes.",
    version,
    permissions: ["storage", "alarms"],
    host_permissions: hostPermissions,
    optional_host_permissions: [
      "*://mercadopublico.cl/Portal/Modules/Site/Buyer/*",
      "*://proveedor.mercadopublico.cl/*",
    ],
    icons: {
      "16": "icons/icon-16.png",
      "32": "icons/icon-32.png",
      "48": "icons/icon-48.png",
      "128": "icons/icon-128.png",
    },
    action: {
      default_title: "Chiripa Licitaciones",
      default_popup: "popup/index.html",
    },
  };

  if (isFirefox) {
    baseManifest.browser_specific_settings = {
      gecko: {
        id: "extension@chiripa.cl",
        strict_min_version: "115.0",
        data_collection_permissions: {
          required: ["none"],
        },
      },
    };
  }

  return baseManifest;
}
