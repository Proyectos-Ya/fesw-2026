import { describe, expect, it } from "vitest";
import { sessionRutFromResourceUrls, waitForSessionRut } from "../compra-agil-session";

const base = "https://servicios-compra-agil.mercadopublico.cl/v1/compra-agil";

describe("sessionRutFromResourceUrls", () => {
  it("toma el RUT de la llamada de la empresa en sesión", () => {
    expect(
      sessionRutFromResourceUrls([
        `${base}/solicitud/1111-22-COT26`,
        `${base}/proveedor/empresa/76.000.000-0`,
      ])
    ).toBe("76.000.000-0");
  });

  it("no confunde otras rutas con RUT ni hosts ajenos", () => {
    expect(
      sessionRutFromResourceUrls([
        "https://servicios-prd.mercadopublico.cl/v3/proveedor/habilidad/76.000.000-0/0",
        "https://evil.example/v1/compra-agil/proveedor/empresa/76.000.000-0",
      ])
    ).toBeNull();
  });

  it("devuelve null si aparecen dos empresas distintas", () => {
    expect(
      sessionRutFromResourceUrls([
        `${base}/proveedor/empresa/76.000.000-0`,
        `${base}/proveedor/empresa/77.000.000-K`,
      ])
    ).toBeNull();
  });
});

describe("waitForSessionRut", () => {
  it("espera a que aparezca la llamada y vence con null", async () => {
    let urls: string[] = [];
    const source = () => urls;
    setTimeout(() => (urls = [`${base}/proveedor/empresa/76.000.000-0`]), 40);
    await expect(waitForSessionRut(source, 1000, 10)).resolves.toBe("76.000.000-0");
    await expect(waitForSessionRut(() => [], 50, 10)).resolves.toBeNull();
  });
});
