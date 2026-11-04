import { describe, expect, it } from "vitest";
import { formatBudget, formatDigestDate, formatVisit } from "../formatDigest";

describe("formatDigest", () => {
  describe("formatDigestDate", () => {
    it("formatea fecha con hora", () => {
      expect(formatDigestDate({ fecha: "2026-10-05", hora: "15:00" })).toBe(
        "05-10-2026, 15:00"
      );
    });

    it("formatea fecha sin hora", () => {
      expect(formatDigestDate({ fecha: "2026-10-05", hora: null })).toBe(
        "05-10-2026"
      );
    });
  });

  describe("formatBudget", () => {
    it("formatea monto con IVA incluido", () => {
      expect(
        formatBudget({
          monto_clp: 5000000,
          incluye_iva: true,
          monto_texto: "x",
        })
      ).toBe("$5.000.000 (IVA incluido)");
    });

    it("formatea monto neto", () => {
      expect(
        formatBudget({
          monto_clp: 5000000,
          incluye_iva: false,
          monto_texto: "x",
        })
      ).toBe("$5.000.000 (neto)");
    });

    it("formatea monto sin especificación de IVA", () => {
      expect(
        formatBudget({
          monto_clp: 5000000,
          incluye_iva: null,
          monto_texto: "x",
        })
      ).toBe("$5.000.000");
    });

    it("usa monto_texto si monto_clp es null", () => {
      expect(
        formatBudget({
          monto_clp: null,
          incluye_iva: null,
          monto_texto: "5 UF",
        })
      ).toBe("5 UF");
    });
  });

  describe("formatVisit", () => {
    it("formatea visita obligatoria completa", () => {
      expect(
        formatVisit({
          obligatoria: true,
          fecha: "2026-10-07",
          hora: "10:00",
          lugar: "Calle 5 s/n",
        })
      ).toBe("Obligatoria · 07-10-2026, 10:00 · Calle 5 s/n");
    });

    it("formatea visita voluntaria", () => {
      expect(
        formatVisit({
          obligatoria: false,
          fecha: null,
          hora: null,
          lugar: null,
        })
      ).toBe("Voluntaria");
    });

    it("devuelve Sin detalle si todo es null", () => {
      expect(
        formatVisit({
          obligatoria: null,
          fecha: null,
          hora: null,
          lugar: null,
        })
      ).toBe("Sin detalle");
    });
  });
});
