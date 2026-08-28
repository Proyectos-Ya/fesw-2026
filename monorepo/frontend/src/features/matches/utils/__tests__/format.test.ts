import { describe, expect, it } from "vitest";

import { formatClosingDate, formatDateTime, parseApiDate } from "../format";

/**
 * El backend persiste todas las fechas en UTC y las serializa con sufijo `Z`.
 * `parseApiDate` además tolera respuestas sin offset (endpoints antiguos),
 * asumiéndolas en UTC según la convención de persistencia.
 *
 * La zona horaria del entorno de test la fija `TZ` en el script de vitest
 * (America/Santiago), que representa al usuario típico de la aplicación.
 */
describe("parseApiDate", () => {
  it("interpreta un ISO con sufijo Z como UTC", () => {
    expect(parseApiDate("2026-07-27T21:42:00Z")?.toISOString()).toBe("2026-07-27T21:42:00.000Z");
  });

  it("interpreta un ISO sin offset como UTC, no como hora local", () => {
    expect(parseApiDate("2026-07-27T21:42:00")?.toISOString()).toBe("2026-07-27T21:42:00.000Z");
  });

  it("conserva los microsegundos truncados a milisegundos", () => {
    expect(parseApiDate("2026-07-27T21:42:00.123456")?.toISOString()).toBe(
      "2026-07-27T21:42:00.123Z",
    );
  });

  it("respeta un offset explícito distinto de UTC", () => {
    expect(parseApiDate("2026-07-27T17:42:00-04:00")?.toISOString()).toBe(
      "2026-07-27T21:42:00.000Z",
    );
  });

  it("acepta una fecha sin componente horario", () => {
    expect(parseApiDate("2026-07-27")?.toISOString()).toBe("2026-07-27T00:00:00.000Z");
  });

  it("devuelve null para valores vacíos o inválidos", () => {
    expect(parseApiDate(null)).toBeNull();
    expect(parseApiDate(undefined)).toBeNull();
    expect(parseApiDate("")).toBeNull();
    expect(parseApiDate("no es una fecha")).toBeNull();
  });
});

/**
 * Sustituye los espacios duros por uno normal antes de comparar.
 *
 * ICU separa el "p. m." con un espacio que no se puede partir en dos líneas, y
 * cuál exactamente depende de la versión: Node 24 emite NO-BREAK SPACE (U+00A0)
 * donde las anteriores ponían uno normal, y otras locales usan el estrecho
 * (U+202F). Los tres se ven idénticos en pantalla —de ahí que el error de
 * vitest muestre dos cadenas aparentemente iguales— y cuál elija ICU no es
 * asunto de la aplicación. Sin esta normalización el mismo test pasa o falla
 * según la versión de Node que tenga instalada cada persona.
 */
function conEspaciosNormales(valor: string): string {
  // Escritos como escapes y no como el carácter literal: en el código fuente
  // un espacio duro es indistinguible de uno corriente, que es justo lo que
  // vuelve difícil de ver este problema.
  return valor.replace(/[\u00a0\u202f]/g, " ");
}

describe("formatDateTime", () => {
  it("muestra la hora convertida a la zona del navegador", () => {
    // 21:42 UTC son las 17:42 en Chile continental durante julio (UTC-4).
    expect(conEspaciosNormales(formatDateTime("2026-07-27T21:42:00Z"))).toBe(
      "27 jul 2026, 05:42 p. m.",
    );
  });

  it("convierte también un ISO sin offset enviado por el backend", () => {
    expect(conEspaciosNormales(formatDateTime("2026-07-27T21:42:00"))).toBe(
      "27 jul 2026, 05:42 p. m.",
    );
  });

  it("aplica el horario de verano cuando corresponde", () => {
    // En enero Chile está en UTC-3: 20:42 UTC son las 17:42 locales.
    expect(conEspaciosNormales(formatDateTime("2026-01-15T20:42:00Z"))).toBe(
      "15 ene 2026, 05:42 p. m.",
    );
  });

  it("devuelve un guion para valores ausentes o inválidos", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime(undefined)).toBe("—");
    expect(formatDateTime("no es una fecha")).toBe("—");
  });
});

describe("formatClosingDate", () => {
  it("usa el día correspondiente a la zona del navegador", () => {
    // 01:00 UTC del día 28 son las 21:00 del día 27 en Chile.
    expect(formatClosingDate("2026-07-28T01:00:00Z")).toBe("27 jul 2026");
  });

  it("devuelve un guion para una fecha inválida", () => {
    expect(formatClosingDate("no es una fecha")).toBe("—");
  });
});
