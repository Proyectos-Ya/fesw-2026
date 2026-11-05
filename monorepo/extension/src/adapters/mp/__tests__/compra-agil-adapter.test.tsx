import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PostulationPackagePayload } from "../../../types/schemas";
import { CompraAgilForm, type CompraAgilFixtureItem } from "../__fixtures__/compra-agil-form";
import { CompraAgilAdapter, parseCompraAgilCode } from "../compra-agil-adapter";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const CODE = "1111-22-COT26";
const RUT = "76.000.000-0";

const fixtureItems: CompraAgilFixtureItem[] = [
  { productId: "42070220", name: "Servicio A", quantity: 1 },
  { productId: "31162800", name: "Insumo B", quantity: 3 },
];

const basePackage = (over: Partial<PostulationPackagePayload> = {}): PostulationPackagePayload => ({
  tender_code: CODE,
  company_rut: RUT,
  company_name: "Empresa de Prueba SpA",
  items: [
    { line_number: 1, product_code: "42070220", name: "Servicio A", quantity: 1, unit_price: 11111, total_price: 11111 },
    { line_number: 2, product_code: "31162800", name: "Insumo B", quantity: 3, unit_price: 2000, total_price: 6000 },
  ],
  total_clp: 17111,
  observations: "Oferta de prueba",
  validity_days: 30,
  delivery_term_days: 5,
  files: [],
  ...over,
});

let container: HTMLDivElement;
let root: Root;

const render = async (items = fixtureItems, code = CODE) => {
  await act(async () => {
    root.render(<CompraAgilForm code={code} items={items} />);
  });
};

const textInputs = () =>
  Array.from(document.querySelectorAll<HTMLInputElement>("input[type='text']:not([disabled])"));
const sendButton = () =>
  Array.from(document.querySelectorAll("button")).find((b) => b.textContent === "Enviar cotización")!;

const fill = async (pkg: PostulationPackagePayload, sessionRut: string | null = RUT) => {
  const adapter = new CompraAgilAdapter(document);
  let result!: Awaited<ReturnType<CompraAgilAdapter["fill"]>>;
  await act(async () => {
    result = await adapter.fill(pkg, { sessionRut });
  });
  return result;
};

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.useRealTimers();
});

describe("parseCompraAgilCode", () => {
  it("extrae el código desde la ruta resumen-cotizacion", () => {
    expect(parseCompraAgilCode(`https://compra-agil.mercadopublico.cl/resumen-cotizacion/${CODE}`)).toBe(CODE);
  });

  it("ignora otros hosts y rutas", () => {
    expect(parseCompraAgilCode(`https://www.mercadopublico.cl/resumen-cotizacion/${CODE}`)).toBeNull();
    expect(parseCompraAgilCode("https://compra-agil.mercadopublico.cl/")).toBeNull();
  });
});

describe("CompraAgilAdapter: hidratación", () => {
  it("no reconoce el formulario antes de que la SPA lo renderice", () => {
    expect(new CompraAgilAdapter(document).isFormReady()).toBe(false);
  });

  it("espera a que aparezca el formulario", async () => {
    const adapter = new CompraAgilAdapter(document);
    const waiting = adapter.waitForForm(2000);
    setTimeout(() => void render(), 50);
    await expect(waiting).resolves.toBe(true);
  });

  it("devuelve false al vencer el plazo", async () => {
    await expect(new CompraAgilAdapter(document).waitForForm(60)).resolves.toBe(false);
  });
});

describe("CompraAgilAdapter: validaciones previas", () => {
  it("no llena nada si el código del encabezado no coincide", async () => {
    await render(fixtureItems, "9999-1-COT26");
    const res = await fill(basePackage());
    expect(res).toMatchObject({ success: false, error: "TENDER_CODE_MISMATCH", filledCount: 0 });
    expect(textInputs()[0].value).toBe("");
  });

  it("no llena nada si no se pudo verificar la empresa de la sesión", async () => {
    await render();
    const res = await fill(basePackage(), null);
    expect(res).toMatchObject({ success: false, error: "IDENTITY_UNVERIFIED" });
    expect(textInputs()[0].value).toBe("");
  });

  it("no llena nada si la empresa de la sesión es otra", async () => {
    await render();
    const res = await fill(basePackage(), "11.111.111-1");
    expect(res).toMatchObject({ success: false, error: "RUT_MISMATCH" });
  });
});

describe("CompraAgilAdapter: llenado", () => {
  it("la fixture reproduce el fallo original: .value directo no llega al estado de React", async () => {
    await render();
    const input = textInputs()[0];
    await act(async () => {
      input.value = "11111";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(document.querySelectorAll<HTMLInputElement>("input[disabled]")[0].value).toBe("");
  });

  it("pega precios y detalle en el estado de React y recalcula totales", async () => {
    await render();
    const res = await fill(basePackage(), "76000000-0");

    expect(res.success).toBe(true);
    const [precioA, precioB] = textInputs();
    expect(precioA.value).toBe("11.111");
    expect(precioB.value).toBe("2.000");
    const subtotals = Array.from(document.querySelectorAll<HTMLInputElement>("input[disabled]"));
    expect(subtotals.map((s) => s.value)).toEqual(["11.111", "6.000"]);
    expect(document.querySelector("[data-testid='total']")?.textContent).toBe("$ 20.362");
    expect(document.querySelector("textarea")?.value).toBe("Oferta de prueba");
    expect(precioA.getAttribute("data-chiripa-field-status")).toBe("filled");
  });

  it("pega el valor de despacho cuando viene en el paquete", async () => {
    await render();
    const res = await fill(basePackage({ shipping_clp: 25000 }));
    const despacho = textInputs()[2];
    expect(despacho.value).toBe("25000");
    expect(despacho.getAttribute("data-chiripa-field-status")).toBe("filled");
    expect(res.pending).not.toContain("Despacho");
  });

  it("recorta el detalle a 255 caracteres", async () => {
    await render();
    await fill(basePackage({ observations: "x".repeat(400) }));
    expect(document.querySelector("textarea")?.value).toHaveLength(255);
  });

  it("marca como pendientes despacho y los ítems sin correspondencia", async () => {
    await render();
    const pkg = basePackage();
    pkg.items = [pkg.items[0]];
    const res = await fill(pkg);

    const [precioA, precioB, despacho] = textInputs();
    expect(precioA.getAttribute("data-chiripa-field-status")).toBe("filled");
    expect(precioB.value).toBe("");
    expect(precioB.getAttribute("data-chiripa-field-status")).toBe("incomplete");
    expect(despacho.getAttribute("data-chiripa-field-status")).toBe("incomplete");
    expect(res.pending).toEqual(expect.arrayContaining(["Insumo B", "Despacho"]));
  });

  it("empareja por orden cuando no hay código de producto y la cantidad de ítems coincide", async () => {
    await render();
    const pkg = basePackage();
    pkg.items = pkg.items.map(({ product_code: _omit, ...it }) => it);
    await fill(pkg);
    expect(textInputs()[1].value).toBe("2.000");
  });

  it("empareja por orden si los códigos vienen de otro catálogo y la cantidad coincide", async () => {
    await render();
    const pkg = basePackage();
    pkg.items = pkg.items.map((it, i) => ({ ...it, product_code: `8310180${i}` }));
    await fill(pkg);
    expect(textInputs()[0].value).toBe("11.111");
    expect(textInputs()[1].value).toBe("2.000");
  });

  it("no empareja por orden si algún código coincide con la página pero otro no", async () => {
    await render();
    const pkg = basePackage();
    pkg.items = [pkg.items[0], { ...pkg.items[1], product_code: "99999999" }];
    await fill(pkg);
    expect(textInputs()[0].value).toBe("11.111");
    expect(textInputs()[1].value).toBe("");
  });

  it("no adivina si los códigos de producto se repiten", async () => {
    await render([fixtureItems[0], { ...fixtureItems[0], name: "Servicio A bis" }]);
    const pkg = basePackage();
    pkg.items = [pkg.items[0]];
    await fill(pkg);
    expect(textInputs()[0].value).toBe("");
    expect(textInputs()[0].getAttribute("data-chiripa-field-status")).toBe("incomplete");
  });

  it("CA8: nunca pulsa «Enviar cotización» aunque quede habilitado", async () => {
    await render();
    const clicks = vi.fn();
    sendButton().addEventListener("click", clicks);
    await fill(basePackage());
    expect(sendButton().disabled).toBe(false);
    expect(clicks).not.toHaveBeenCalled();
  });
});

describe("CompraAgilAdapter: vigencia y adjuntos", () => {
  it("fija la vigencia en hoy + validity_days con formato dd/mm/aaaa", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 10, 4, 12, 0, 0));
    await render();
    await fill(basePackage({ validity_days: 10 }));
    const vigencia = document.getElementById(":r0:") as HTMLInputElement;
    expect(vigencia.value).toBe("14/11/2026");
    expect(vigencia.getAttribute("data-chiripa-field-status")).toBe("filled");
  });

  it("no sube anexos al llenar: quedan pendientes hasta que el usuario confirme", async () => {
    await render();
    const pdf = btoa("%PDF-1.7 prueba");
    const res = await fill(
      basePackage({ files: [{ name: "propuesta-tecnica.pdf", type: "application/pdf", size: 15, data_base64: pdf }] })
    );
    const fileInput = document.querySelector<HTMLInputElement>("input[type='file']")!;
    expect(fileInput.files?.length ?? 0).toBe(0);
    expect(res.pending).toContain("propuesta-tecnica.pdf");
    expect(res.annexReady).toBe("propuesta-tecnica.pdf");
  });

  it("attachAnnex adjunta el primer archivo aceptado tras la confirmación", async () => {
    await render();
    const adapter = new CompraAgilAdapter(document);
    let res!: Awaited<ReturnType<CompraAgilAdapter["attachAnnex"]>>;
    await act(async () => {
      res = await adapter.attachAnnex([
        { name: "foto.png", type: "image/png", size: 10, data_base64: btoa("x") },
        { name: "grande.pdf", type: "application/pdf", size: 21 * 1024 * 1024, data_base64: btoa("x") },
        { name: "uno.pdf", type: "application/pdf", size: 1, data_base64: btoa("x") },
        { name: "dos.pdf", type: "application/pdf", size: 1, data_base64: btoa("x") },
      ]);
    });
    const fileInput = document.querySelector<HTMLInputElement>("input[type='file']")!;
    expect(fileInput.files?.[0]?.name).toBe("uno.pdf");
    expect(fileInput.getAttribute("data-chiripa-field-status")).toBe("filled");
    expect(res).toEqual({ attached: "uno.pdf", pending: ["foto.png", "grande.pdf", "dos.pdf"] });
  });
});
