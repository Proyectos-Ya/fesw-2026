export type SupportedBrowser = "chrome" | "firefox" | "edge" | "safari" | "other";

export const CHROME_WEB_STORE_URL =
  "https://chromewebstore.google.com/detail/chiripa-licitaciones-inte/extension-chiripa-id";

export const FIREFOX_AMO_URL =
  "https://addons.mozilla.org/es/firefox/addon/chiripa/";

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
