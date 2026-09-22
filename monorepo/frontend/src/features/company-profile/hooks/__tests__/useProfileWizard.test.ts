import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useProfileWizard } from "../useProfileWizard";
import type { CompanyProfileImport } from "../../services/supplierService";

const IMPORTED: CompanyProfileImport = {
  source: "sre",
  rut: "76668304-5",
  legal_name: "Planeta Libre Soluciones Sustentables Limitada",
  is_active: null,
  regions: [],
  sectors: ["Obras de Construcción e Infraestructura", "Mantención y Reparación"],
  keywords: ["pintura"],
  notices: [],
};

describe("useProfileWizard", () => {
  it("empieza sin datos importados", () => {
    const { result } = renderHook(() => useProfileWizard());
    expect(result.current.importedProfile).toBeNull();
  });

  it("guarda la importación y marca los rubros sin perder los ya elegidos", () => {
    const { result } = renderHook(() => useProfileWizard());

    act(() => result.current.nextStep({ sectors: ["Mantención y Reparación"] }));
    act(() => result.current.applyImport(IMPORTED));

    expect(result.current.importedProfile).toEqual(IMPORTED);
    expect(result.current.formData.sectors).toEqual([
      "Mantención y Reparación",
      "Obras de Construcción e Infraestructura",
    ]);
  });

  it("importar no cambia de paso ni toca las palabras clave", () => {
    const { result } = renderHook(() => useProfileWizard());

    act(() => result.current.applyImport(IMPORTED));

    expect(result.current.currentStep).toBe(1);
    expect(result.current.formData.keywords).toEqual([]);
  });
});
