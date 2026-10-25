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
  sectors: ["Servicios de construcción y mantenimiento", "Servicios de limpieza industrial"],
  keywords: ["pintura"],
  notices: [],
};

const WITH_REGIONS: CompanyProfileImport = {
  ...IMPORTED,
  regions: ["Metropolitana"],
  sectors: ["Servicios de construcción y mantenimiento"],
};

describe("useProfileWizard", () => {
  it("empieza sin datos importados", () => {
    const { result } = renderHook(() => useProfileWizard());
    expect(result.current.importedProfile).toBeNull();
  });

  it("guarda la importación y suma los rubros sin perder los ya elegidos", () => {
    const { result } = renderHook(() => useProfileWizard());

    act(() => result.current.nextStep({ sectors: ["Servicios de limpieza industrial"] }));
    act(() => result.current.applyImport(IMPORTED));

    expect(result.current.importedProfile).toEqual(IMPORTED);
    expect(result.current.formData.sectors).toEqual([
      "Servicios de limpieza industrial",
      "Servicios de construcción y mantenimiento",
    ]);
  });

  it("importar no cambia de paso ni toca las palabras clave", () => {
    const { result } = renderHook(() => useProfileWizard());

    act(() => result.current.applyImport(IMPORTED));

    expect(result.current.currentStep).toBe(1);
    expect(result.current.formData.keywords).toEqual([]);
  });

  describe("IMPORT aplica el borrador (T6)", () => {
    it("reemplaza la razón social y deja los tres campos pendientes", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.nextStep({ legal_name: "Nombre escrito a mano" }));

      act(() => result.current.applyImport(WITH_REGIONS));

      expect(result.current.formData.legal_name).toBe(WITH_REGIONS.legal_name);
      expect(result.current.importReview.status).toEqual({
        legal_name: "pending",
        regions: "pending",
        sectors: "pending",
      });
    });

    it("conserva la razón social si la fuente no trae una", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.nextStep({ legal_name: "Nombre escrito a mano" }));

      act(() => result.current.applyImport({ ...WITH_REGIONS, legal_name: "  " }));

      expect(result.current.formData.legal_name).toBe("Nombre escrito a mano");
      expect(result.current.importReview.status.legal_name).toBeUndefined();
    });

    it("suma regiones y rubros sin duplicar y descarta lo que no está en el catálogo", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.nextStep({ regions: ["Valparaíso"], sectors: [] }));

      act(() =>
        result.current.applyImport({
          ...WITH_REGIONS,
          regions: ["Valparaíso", "Metropolitana", "Atlántida"],
          sectors: ["Servicios de limpieza industrial", "Rubro inventado"],
        }),
      );

      expect(result.current.formData.regions).toEqual(["Valparaíso", "Metropolitana"]);
      expect(result.current.formData.sectors).toEqual(["Servicios de limpieza industrial"]);
      expect(result.current.importReview.added).toEqual({
        regions: ["Metropolitana"],
        sectors: ["Servicios de limpieza industrial"],
      });
    });

    it("no deja pendiente un campo al que la importación no aportó nada", () => {
      const { result } = renderHook(() => useProfileWizard());

      act(() => result.current.applyImport({ ...WITH_REGIONS, regions: [], sectors: [] }));

      expect(result.current.importReview.status).toEqual({ legal_name: "pending" });
      expect(result.current.isStepBlocked(2)).toBe(false);
      expect(result.current.isStepBlocked(3)).toBe(false);
    });

    it("no marca las palabras clave", () => {
      const { result } = renderHook(() => useProfileWizard());

      act(() => result.current.applyImport(WITH_REGIONS));

      expect(result.current.formData.keywords).toEqual([]);
    });
  });

  describe("IMPORT con otro RUT (T7)", () => {
    it("vacía razón social, regiones y rubros antes de aplicar la importación nueva", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.applyImport(WITH_REGIONS));
      act(() => result.current.nextStep({ regions: [...(result.current.formData.regions ?? []), "Ñuble"] }));

      act(() =>
        result.current.applyImport({
          ...WITH_REGIONS,
          rut: "76086428-5",
          legal_name: "Otra Empresa SpA",
          regions: ["Biobío"],
          sectors: [],
        }),
      );

      expect(result.current.formData.legal_name).toBe("Otra Empresa SpA");
      expect(result.current.formData.regions).toEqual(["Biobío"]);
      expect(result.current.formData.sectors).toEqual([]);
      expect(result.current.importReview.rut).toBe("76.086.428-5");
      expect(result.current.importReview.added).toEqual({ regions: ["Biobío"], sectors: [] });
    });

    it("con otro RUT que no trae razón social deja la razón social vacía", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.applyImport(WITH_REGIONS));

      act(() => result.current.applyImport({ ...WITH_REGIONS, rut: "76086428-5", legal_name: "" }));

      expect(result.current.formData.legal_name).toBe("");
      expect(result.current.importReview.status.legal_name).toBeUndefined();
    });

    it("con el mismo RUT escrito con otro formato no vacía nada y vuelve a dejar pendiente", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.applyImport(WITH_REGIONS));
      act(() => result.current.confirmField("legal_name"));
      act(() => result.current.confirmField("regions"));
      act(() => result.current.nextStep({ regions: [...(result.current.formData.regions ?? []), "Ñuble"] }));

      act(() => result.current.applyImport({ ...WITH_REGIONS, rut: "76.668.304-5" }));

      expect(result.current.formData.regions).toEqual(["Metropolitana", "Ñuble"]);
      expect(result.current.importReview.status.legal_name).toBe("pending");
      expect(result.current.importReview.status.regions).toBe("pending");
      expect(result.current.importReview.added.regions).toEqual(["Metropolitana"]);
    });
  });

  describe("revisión por campo (T8)", () => {
    it("confirmar y editar cambian el estado del campo", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.applyImport(WITH_REGIONS));

      act(() => result.current.editField("regions"));
      expect(result.current.importReview.status.regions).toBe("editing");

      act(() => result.current.confirmField("regions"));
      expect(result.current.importReview.status.regions).toBe("confirmed");
    });

    it("confirmar un campo que no está en revisión no hace nada", () => {
      const { result } = renderHook(() => useProfileWizard());

      act(() => result.current.confirmField("regions"));

      expect(result.current.importReview.status).toEqual({});
    });

    it("isStepBlocked es verdadero con un campo pendiente o en edición del paso", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.applyImport(WITH_REGIONS));

      expect(result.current.isStepBlocked(1)).toBe(true);
      expect(result.current.isStepBlocked(2)).toBe(true);
      expect(result.current.isStepBlocked(3)).toBe(true);
      expect(result.current.isStepBlocked(4)).toBe(false);

      act(() => result.current.confirmField("legal_name"));
      act(() => result.current.editField("regions"));
      act(() => result.current.confirmField("sectors"));

      expect(result.current.isStepBlocked(1)).toBe(false);
      expect(result.current.isStepBlocked(2)).toBe(true);
      expect(result.current.isStepBlocked(3)).toBe(false);
    });

    it("borrar la razón social la vacía y saca el campo de revisión", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.applyImport(WITH_REGIONS));

      act(() => result.current.clearField("legal_name"));

      expect(result.current.formData.legal_name).toBe("");
      expect(result.current.importReview.status.legal_name).toBeUndefined();
      expect(result.current.isStepBlocked(1)).toBe(false);
    });

    it("borrar regiones quita solo las que trajo la importación", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.nextStep({ regions: ["Valparaíso"] }));
      act(() => result.current.applyImport(WITH_REGIONS));

      act(() => result.current.clearField("regions"));

      expect(result.current.formData.regions).toEqual(["Valparaíso"]);
      expect(result.current.importReview.added.regions).toEqual([]);
      expect(result.current.importReview.status.regions).toBeUndefined();
    });

    it("borrar rubros quita solo los que trajo la importación", () => {
      const { result } = renderHook(() => useProfileWizard());
      act(() => result.current.nextStep({ sectors: ["Servicios de limpieza industrial"] }));
      act(() => result.current.applyImport(WITH_REGIONS));

      act(() => result.current.clearField("sectors"));

      expect(result.current.formData.sectors).toEqual(["Servicios de limpieza industrial"]);
      expect(result.current.importReview.added.sectors).toEqual([]);
    });
  });

  it("empieza sin palabras clave descartadas", () => {
    const { result } = renderHook(() => useProfileWizard());
    expect(result.current.dismissedKeywords).toEqual([]);
  });

  it("recuerda las palabras clave descartadas al cambiar de paso", () => {
    const { result } = renderHook(() => useProfileWizard());

    act(() => result.current.dismissKeyword("pintura"));
    act(() => result.current.nextStep({}));
    act(() => result.current.prevStep());

    expect(result.current.dismissedKeywords).toEqual(["pintura"]);
  });

  it("no repite una palabra clave descartada dos veces, sin importar mayúsculas", () => {
    const { result } = renderHook(() => useProfileWizard());

    act(() => result.current.dismissKeyword("Pintura"));
    act(() => result.current.dismissKeyword(" pintura "));

    expect(result.current.dismissedKeywords).toEqual(["Pintura"]);
  });
});
