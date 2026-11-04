import { afterEach, describe, expect, it, vi } from "vitest";

import { InsecureContextError, sha256Hex } from "../sha256";

describe("sha256Hex", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calcula la huella de un archivo", async () => {
    expect(await sha256Hex(new File(["hola"], "a.pdf"))).toBe(
      "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79",
    );
  });

  it("la de un archivo vacío es la conocida", async () => {
    expect(await sha256Hex(new File([], "vacio.pdf"))).toBe(
      "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    );
  });

  it("sin WebCrypto explica que hay que abrir Chiripa por https o localhost", async () => {
    vi.stubGlobal("crypto", {});

    const error = await sha256Hex(new File(["hola"], "a.pdf")).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(InsecureContextError);
    expect((error as Error).message).toMatch(/https o localhost/);
  });
});
