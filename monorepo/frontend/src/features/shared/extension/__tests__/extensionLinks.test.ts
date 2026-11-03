import { describe, expect, it } from "vitest";
import { detectBrowser, getExtensionStoreUrl } from "../extensionLinks";

describe("extensionLinks", () => {
  it("retorna enlace de Chrome Web Store para Chrome y Edge", () => {
    expect(getExtensionStoreUrl("chrome")).toContain("chromewebstore.google.com");
    expect(getExtensionStoreUrl("edge")).toContain("chromewebstore.google.com");
  });

  it("retorna enlace de Firefox Add-ons para Firefox", () => {
    expect(getExtensionStoreUrl("firefox")).toContain("addons.mozilla.org");
  });

  it("retorna null para navegadores no soportados como Safari o móvil", () => {
    expect(getExtensionStoreUrl("safari")).toBeNull();
    expect(getExtensionStoreUrl("other")).toBeNull();
  });

  it("detectBrowser clasifica el userAgent adecuadamente", () => {
    const chromeUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
    const firefoxUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0";
    const edgeUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0";

    expect(detectBrowser(chromeUA)).toBe("chrome");
    expect(detectBrowser(firefoxUA)).toBe("firefox");
    expect(detectBrowser(edgeUA)).toBe("edge");
  });
});
