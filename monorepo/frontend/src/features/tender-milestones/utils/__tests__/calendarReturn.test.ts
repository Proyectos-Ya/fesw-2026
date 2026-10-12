import { afterEach, describe, expect, it, vi } from "vitest";

import {
  consumeCalendarReturnTender,
  consumePendingCalendarSync,
  rememberCalendarReturnTender,
  savePendingCalendarSync,
} from "../calendarReturn";

describe("calendarReturn", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
  });

  it("recuerda la licitación de la que se salió a autorizar, una sola vez", () => {
    rememberCalendarReturnTender("t-1");

    expect(consumeCalendarReturnTender()).toBe("t-1");
    expect(consumeCalendarReturnTender()).toBeNull();
  });

  it("si el almacenamiento no está disponible no falla", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });

    expect(() => rememberCalendarReturnTender("t-1")).not.toThrow();
    expect(consumeCalendarReturnTender()).toBeNull();
  });

  it("lo pendiente solo lo consume el proveedor con el que se autorizó", () => {
    // Con Google y Outlook en la misma ficha, al volver de Microsoft el hook de
    // Google no debe llevarse la sincronización.
    savePendingCalendarSync({
      provider: "outlook",
      tender_id: "t-1",
      milestone_ids: ["m-1"],
      default_time: null,
      account_email: "u@outlook.com",
    });

    expect(consumePendingCalendarSync("t-1", "google")).toBeNull();
    expect(consumePendingCalendarSync("t-1", "outlook")).toMatchObject({ provider: "outlook" });
    expect(consumePendingCalendarSync("t-1", "outlook")).toBeNull();
  });
});
