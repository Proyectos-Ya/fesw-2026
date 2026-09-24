import { describe, expect, it } from "vitest";

import { formatMilestoneDate, urgencyBadge } from "../milestoneFormat";

const AHORA = new Date("2026-10-01T15:00:00Z"); // 12:00 en Chile

describe("formatMilestoneDate", () => {
  it("muestra fecha y hora de Chile cuando el hito tiene hora", () => {
    expect(formatMilestoneDate("2026-10-20T18:00:00Z", true)).toBe("20 oct 2026, 15:00");
  });

  it("muestra solo la fecha cuando el hito no tiene hora", () => {
    // Sin hora, el backend lo guarda a medianoche de Chile (03:00 UTC en octubre).
    expect(formatMilestoneDate("2026-10-20T03:00:00Z", false)).toBe("20 oct 2026");
  });

  it("devuelve un guion si la fecha no es válida", () => {
    expect(formatMilestoneDate("no-es-fecha", true)).toBe("—");
  });
});

describe("urgencyBadge", () => {
  it("un hito vencido se muestra como vencido", () => {
    expect(urgencyBadge("vencido", "2026-09-30T15:00:00Z", AHORA)).toEqual({
      label: "Vencido",
      tone: "neutral",
    });
  });

  it("un hito crítico de hoy se destaca en rojo", () => {
    expect(urgencyBadge("critico", "2026-10-01T20:00:00Z", AHORA)).toEqual({
      label: "Hoy",
      tone: "danger",
    });
  });

  it("un hito crítico de mañana dice mañana", () => {
    expect(urgencyBadge("critico", "2026-10-02T15:00:00Z", AHORA)).toEqual({
      label: "Mañana",
      tone: "danger",
    });
  });

  it("un hito próximo se destaca en amarillo con los días que faltan", () => {
    expect(urgencyBadge("proximo", "2026-10-06T15:00:00Z", AHORA)).toEqual({
      label: "En 5 días",
      tone: "warning",
    });
  });

  it("un hito lejano no se destaca", () => {
    expect(urgencyBadge("normal", "2026-10-21T15:00:00Z", AHORA)).toEqual({
      label: "En 20 días",
      tone: "neutral",
    });
  });
});
