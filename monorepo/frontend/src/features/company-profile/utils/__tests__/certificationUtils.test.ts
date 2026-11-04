import { describe, expect, it } from "vitest";
import { getCertificationStatus } from "../certification";

// 15 de junio de 2026, a mediodía hora local.
const REFERENCE = new Date(2026, 5, 15, 12, 0, 0);

describe("getCertificationStatus", () => {
  it("devuelve no_date cuando no hay fecha", () => {
    expect(getCertificationStatus(null, REFERENCE).status).toBe("no_date");
    expect(getCertificationStatus(undefined, REFERENCE).status).toBe("no_date");
    expect(getCertificationStatus("", REFERENCE).status).toBe("no_date");
  });

  it("devuelve no_date con strings inválidos", () => {
    expect(getCertificationStatus("no-es-fecha", REFERENCE).status).toBe("no_date");
    expect(getCertificationStatus("2026-13-40", REFERENCE).status).toBe("no_date");
    expect(getCertificationStatus("2026-02-31", REFERENCE).status).toBe("no_date");
  });

  it("marca como vencida una fecha pasada", () => {
    const result = getCertificationStatus("2026-06-14", REFERENCE);
    expect(result.status).toBe("expired");
    expect(result.label).toBe("Vencida");
    expect(result.daysLeft).toBe(-1);
  });

  it("marca como por vencer una fecha de hoy aunque ya pasara su hora", () => {
    const late = new Date(2026, 5, 15, 23, 59, 59);
    const result = getCertificationStatus("2026-06-15", late);
    expect(result.status).toBe("expiring_soon");
    expect(result.daysLeft).toBe(0);
    expect(result.label).toBe("Vence hoy");
  });

  it("marca como por vencer una fecha en 1 día", () => {
    const result = getCertificationStatus("2026-06-16", REFERENCE);
    expect(result.status).toBe("expiring_soon");
    expect(result.daysLeft).toBe(1);
    expect(result.label).toBe("Vence en 1 día");
  });

  it("marca como por vencer una fecha en exactamente 30 días", () => {
    const result = getCertificationStatus("2026-07-15", REFERENCE);
    expect(result.status).toBe("expiring_soon");
    expect(result.daysLeft).toBe(30);
    expect(result.label).toBe("Vence en 30 días");
  });

  it("marca como vigente una fecha en 31 días", () => {
    const result = getCertificationStatus("2026-07-16", REFERENCE);
    expect(result.status).toBe("valid");
    expect(result.daysLeft).toBe(31);
  });

  it("acepta un datetime ISO usando solo la parte de fecha", () => {
    expect(getCertificationStatus("2026-06-20T00:00:00Z", REFERENCE).daysLeft).toBe(5);
  });

  it("usa el reloj real cuando no se inyecta referenceDate", () => {
    expect(getCertificationStatus("2000-01-01").status).toBe("expired");
    expect(getCertificationStatus("2999-01-01").status).toBe("valid");
  });
});
