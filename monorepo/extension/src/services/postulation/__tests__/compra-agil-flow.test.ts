import { describe, expect, it, vi } from "vitest";
import { PostulationPackagePayload } from "../../../types/schemas";
import { runCompraAgilFlow, type CompraAgilFlowDeps } from "../compra-agil-flow";

const pkg = {
  tender_code: "1111-22-COT26",
  company_rut: "76.000.000-0",
  files: [{ name: "anexo.pdf", type: "application/pdf", size: 1, data_base64: "eA==" }],
} as PostulationPackagePayload;

const makeDeps = (over: Partial<CompraAgilFlowDeps> = {}): CompraAgilFlowDeps => ({
  tenderCode: "1111-22-COT26",
  waitForForm: vi.fn().mockResolvedValue(true),
  getPackage: vi.fn().mockResolvedValue(pkg),
  getSessionRut: vi.fn().mockResolvedValue("76.000.000-0"),
  fill: vi.fn().mockResolvedValue({ success: true, filledCount: 3, incompleteCount: 1, pending: ["Despacho"] }),
  attachAnnex: vi.fn().mockResolvedValue({ attached: "anexo.pdf", pending: [] }),
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

  it("solo sube el anexo cuando el usuario confirma en el panel", async () => {
    const deps = makeDeps({
      fill: vi.fn().mockResolvedValue({
        success: true,
        filledCount: 3,
        incompleteCount: 2,
        pending: ["Despacho", "anexo.pdf"],
        annexReady: "anexo.pdf",
      }),
    });
    await runCompraAgilFlow(deps);
    expect(deps.attachAnnex).not.toHaveBeenCalled();

    const first = vi.mocked(deps.render).mock.calls[0][0];
    expect(first.annexToConfirm).toBe("anexo.pdf");
    await first.onConfirmAnnex!();

    expect(deps.attachAnnex).toHaveBeenCalledTimes(1);
    expect(deps.render).toHaveBeenLastCalledWith(
      expect.objectContaining({ filledCount: 4, incompleteCount: 1, pending: ["Despacho"], annexToConfirm: undefined })
    );
  });
});
