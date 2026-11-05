import { describe, expect, it } from "vitest";
import { buildManifest } from "../manifest";

describe("buildManifest", () => {
  it("en modo produccion no incluye localhost ni cookies ni dominios de login", () => {
    const manifest = buildManifest({ mode: "production", browser: "chrome" });

    // Permisos
    expect(manifest.permissions).not.toContain("cookies");
    expect(manifest.permissions).toContain("storage");
    expect(manifest.permissions).toContain("alarms");

    // Hosts
    const hosts = (manifest.host_permissions as string[]) ?? [];
    expect(hosts.some((h: string) => h.includes("localhost"))).toBe(false);
    expect(hosts.some((h: string) => h.includes("claveunica"))).toBe(false);
    expect(hosts.some((h: string) => h.includes("login"))).toBe(false);

    // Origenes validos
    expect(hosts).toContain("*://*.mercadopublico.cl/*");
    expect(hosts).toContain("*://*.chiripa.cl/*");
    expect(hosts).not.toContain("*://*.vercel.app/*");
  });

  it("en modo e2e o dev incluye localhost:3000", () => {
    const manifest = buildManifest({ mode: "development", browser: "chrome" });
    const hosts = (manifest.host_permissions as string[]) ?? [];
    expect(hosts).toContain("http://localhost:3000/*");
  });

  it("en Firefox incluye browser_specific_settings con gecko.id y data_collection_permissions", () => {
    const manifest = buildManifest({ mode: "production", browser: "firefox" }) as Record<string, unknown>;
    const gecko = (manifest.browser_specific_settings as { gecko?: { id?: string; strict_min_version?: string; data_collection_permissions?: unknown } })?.gecko;
    expect(gecko?.id).toBe("extension@chiripa.cl");
    expect(gecko?.strict_min_version).toBe("115.0");
    expect(gecko?.data_collection_permissions).toBeDefined();
  });

  it("incluye los 4 iconos requeridos por las tiendas", () => {
    const manifest = buildManifest({ mode: "production", browser: "chrome" });
    expect(manifest.icons).toEqual({
      "16": "icons/icon-16.png",
      "32": "icons/icon-32.png",
      "48": "icons/icon-48.png",
      "128": "icons/icon-128.png",
    });
  });

  it("los orígenes web del bridge no incluyen comodines de hosting compartido", async () => {
    const { CHIRIPA_WEB_MATCHES } = await import("../web-origins");
    expect(CHIRIPA_WEB_MATCHES).toContain("*://*.chiripa.cl/*");
    expect(CHIRIPA_WEB_MATCHES.some((m) => m.includes("*.vercel.app"))).toBe(false);
    expect(CHIRIPA_WEB_MATCHES).toContain("https://fesw-2026-zeta.vercel.app/*");
    expect(CHIRIPA_WEB_MATCHES).toContain(
      "https://fesw-2026-git-develop-benjaminulloaf-5015s-projects.vercel.app/*"
    );
    const manifest = buildManifest({ mode: "production", browser: "chrome" });
    const hosts = (manifest.host_permissions as string[]) ?? [];
    for (const m of CHIRIPA_WEB_MATCHES) expect(hosts).toContain(m);
  });
});
