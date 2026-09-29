import { afterEach, describe, expect, it, vi } from "vitest";

import { consumeCalendarReturnTender, rememberCalendarReturnTender } from "../calendarReturn";

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
});
