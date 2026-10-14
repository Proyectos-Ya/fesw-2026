import { describe, expect, it } from "vitest";

import { callClosingLines, isSecondCall, SECOND_CALL_LABEL } from "../secondCall";

/**
 * Octubre es UTC-3 en Chile: 16:30 UTC son las 13:30 y 16:40 UTC las 13:40.
 */
const PRIMER = "2026-10-06T16:30:00Z";
const SEGUNDO = "2026-10-07T16:40:00Z";

/**
 * `Intl` separa la hora del "p. m." con un espacio duro o uno fino según la
 * versión de Node. Escritos como escapes y no como el carácter literal: en el
 * código fuente son indistinguibles de un espacio corriente.
 */
function conEspaciosNormales(valor: string): string {
  return valor.replace(/[\u00a0\u202f]/g, " ");
}

describe("isSecondCall", () => {
  it("solo lo afirma un 2 explícito", () => {
    expect(isSecondCall({ call_number: 2 })).toBe(true);
  });

  it("el primer llamado, el nulo y la ausencia no son segundo llamado", () => {
    expect(isSecondCall({ call_number: 1 })).toBe(false);
    expect(isSecondCall({ call_number: null })).toBe(false);
    expect(isSecondCall({})).toBe(false);
  });
});

describe("SECOND_CALL_LABEL", () => {
  it("es el texto de la etiqueta", () => {
    expect(SECOND_CALL_LABEL).toBe("Segundo llamado");
  });
});

describe("callClosingLines", () => {
  it("sin fechas por llamado no devuelve nada", () => {
    expect(callClosingLines({})).toEqual([]);
    expect(
      callClosingLines({
        call_number: null,
        first_call_closing_at: null,
        second_call_closing_at: null,
      }),
    ).toEqual([]);
  });

  it("en el primer llamado la fecha del segundo es solo posible", () => {
    const lines = callClosingLines({
      call_number: 1,
      first_call_closing_at: PRIMER,
      second_call_closing_at: SEGUNDO,
    });

    expect(lines.map((l) => l.label)).toEqual(["Cierre 1.er llamado", "Segundo llamado posible"]);
    expect(lines.map((l) => conEspaciosNormales(l.value))).toEqual([
      "06 oct 2026, 01:30 p. m.",
      "07 oct 2026, 01:40 p. m.",
    ]);
    expect(lines[0].hint).toBeUndefined();
    expect(lines[1].hint).toBeTruthy();
  });

  it("en el segundo llamado ambas fechas son plazos y ninguna lleva aclaración", () => {
    const lines = callClosingLines({
      call_number: 2,
      first_call_closing_at: PRIMER,
      second_call_closing_at: SEGUNDO,
    });

    expect(lines.map((l) => l.label)).toEqual(["Cierre 1.er llamado", "Cierre 2.º llamado"]);
    expect(lines.every((l) => l.hint === undefined)).toBe(true);
  });

  it("una licitación antigua con solo una fecha muestra solo esa línea", () => {
    const lines = callClosingLines({ second_call_closing_at: SEGUNDO });

    expect(lines.map((l) => l.key)).toEqual(["second"]);
  });

  it("una fecha ilegible se omite", () => {
    const lines = callClosingLines({
      call_number: 1,
      first_call_closing_at: "x",
      second_call_closing_at: SEGUNDO,
    });

    expect(lines.map((l) => l.key)).toEqual(["second"]);
  });
});
