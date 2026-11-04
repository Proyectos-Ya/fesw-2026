import { describe, expect, it, vi } from "vitest";
import { PostulationPackagePayload } from "../../../types/schemas";
import { runCompraAgilFlow, type CompraAgilFlowDeps } from "../compra-agil-flow";

const pkg = { tender_code: "1111-22-COT26", company_rut: "76.000.000-0" } as PostulationPackagePayload;

const makeDeps = (over: Partial<CompraAgilFlowDeps> = {}): CompraAgilFlowDeps => ({
  tenderCode: "1111-22-COT26",
  waitForForm: vi.fn().mockResolvedValue(true),
  getPackage: vi.fn().mockResolvedValue(pkg),
  getSessionRut: vi.fn().mockResolvedValue("76.000.000-0"),
  fill: vi.fn().mockResolvedValue({ success: true, filledCount: 3, incompleteCount: 1, pending: ["Despacho"] }),
  render: vi.fn(),
  ...over,
});

describe("runCompraAgilFlow", () => {
  it("espera el formulario, verifica la sesión, llena y muestra el resumen", async () => {
    const deps = makeDeps();
    await runCompraAgilFlow(deps);
    expect(deps.getPackage).toHaveBeenCalledWith("1111-22-COT26");
    expect(deps.fill).toHaveBeenCalledWith(pkg, { sessionRut: "76.000.000-0" });
    expect(deps.render).toHaveBeenCalledWith(
      expect.objectContaining({ packageData: pkg, filledCount: 3, pending: ["Despacho"] })
    );
  });

  it("no hace nada si no hay paquete pendiente para la cotización", async () => {
    const deps = makeDeps({ getPackage: vi.fn().mockResolvedValue(null) });
    await runCompraAgilFlow(deps);
    expect(deps.waitForForm).not.toHaveBeenCalled();
    expect(deps.fill).not.toHaveBeenCalled();
    expect(deps.render).not.toHaveBeenCalled();
  });

  it("avisa en el panel si el formulario no aparece", async () => {
    const deps = makeDeps({ waitForForm: vi.fn().mockResolvedValue(false) });
    await runCompraAgilFlow(deps);
    expect(deps.fill).not.toHaveBeenCalled();
    expect(deps.render).toHaveBeenCalledWith(expect.objectContaining({ notice: expect.stringContaining("formulario") }));
  });

  it("avisa en el panel y no llena si la empresa de la sesión no coincide", async () => {
    const deps = makeDeps({
      fill: vi.fn().mockResolvedValue({ success: false, filledCount: 0, incompleteCount: 0, pending: [], error: "RUT_MISMATCH" }),
    });
    await runCompraAgilFlow(deps);
    expect(deps.render).toHaveBeenCalledWith(expect.objectContaining({ notice: expect.stringContaining("empresa") }));
  });
});
