export type SupportedBrowser = "chrome" | "firefox" | "edge" | "safari" | "other";

export const CHROME_WEB_STORE_URL =
  "https://chromewebstore.google.com/detail/chiripa-licitaciones-inte/extension-chiripa-id";

export const FIREFOX_AMO_URL =
  "https://addons.mozilla.org/es/firefox/addon/chiripa/";

/**
 * Cómo se instala la extensión. Mientras no esté publicada en las tiendas se descarga
 * el .zip que sirve el frontend (`public/extension/`, ver `pnpm run release:zips` en
 * monorepo/extension). Al publicarla, cambiar a "store".
 */
export const EXTENSION_DISTRIBUTION: "zip" | "store" = "zip";

const ZIP_URLS = {
  chromium: "/extension/chiripa-chrome.zip",
  firefox: "/extension/chiripa-firefox.zip",
} as const;

export function detectBrowser(userAgentString?: string): SupportedBrowser {
  const ua = (userAgentString ?? (typeof navigator !== "undefined" ? navigator.userAgent : "")).toLowerCase();

  if (ua.includes("edg/")) {
    return "edge";
  }
  if (ua.includes("firefox")) {
    return "firefox";
  }
  if (ua.includes("chrome") && !ua.includes("edg/")) {
    return "chrome";
  }
  if (ua.includes("safari") && !ua.includes("chrome")) {
    return "safari";
  }
  return "other";
}

export function getExtensionStoreUrl(browser: SupportedBrowser): string | null {
  switch (browser) {
    case "chrome":
    case "edge":
      return CHROME_WEB_STORE_URL;
    case "firefox":
      return FIREFOX_AMO_URL;
    default:
      return null;
  }
}

/** .zip de la extensión para el navegador (Chrome y Edge usan el mismo). */
export function getExtensionZipUrl(browser: SupportedBrowser): string | null {
  switch (browser) {
    case "chrome":
    case "edge":
      return ZIP_URLS.chromium;
    case "firefox":
      return ZIP_URLS.firefox;
    default:
      return null;
  }
}

/** Enlace de instalación según la distribución vigente. */
export function getExtensionInstallUrl(browser: SupportedBrowser): string | null {
  return EXTENSION_DISTRIBUTION === "zip" ? getExtensionZipUrl(browser) : getExtensionStoreUrl(browser);
}

