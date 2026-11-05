import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExtensionStorage } from "../extension-storage";

/**
 * En Firefox (MV2) el espacio `chrome.*` funciona con callbacks y no devuelve promesas:
 * `await chrome.storage.local.get(...)` da undefined. Se simula esa API.
 */
function callbackOnlyStorage() {
  const data: Record<string, unknown> = {};
  return {
    get: (keys: string[] | null, cb?: (items: Record<string, unknown>) => void) => {
      const out = keys ? Object.fromEntries(keys.filter((k) => k in data).map((k) => [k, data[k]])) : { ...data };
      setTimeout(() => cb?.(out), 0);
      return undefined;
    },
    set: (items: Record<string, unknown>, cb?: () => void) => {
      Object.assign(data, items);
      setTimeout(() => cb?.(), 0);
      return undefined;
    },
    remove: (keys: string[], cb?: () => void) => {
      for (const k of keys) delete data[k];
      setTimeout(() => cb?.(), 0);
      return undefined;
    },
  };
}

describe("ExtensionStorage con la API de callbacks de Firefox", () => {
  const original = (globalThis as { chrome?: unknown }).chrome;

  beforeEach(() => {
    vi.stubGlobal("chrome", { storage: { local: callbackOnlyStorage() } });
  });

  afterEach(() => {
    vi.stubGlobal("chrome", original);
  });

  it("guarda y lee la vinculación", async () => {
    await ExtensionStorage.saveCredentials({ apiUrl: "http://localhost:8000", accessToken: "tok", installationId: "i-1" });
    await expect(ExtensionStorage.getCredentials()).resolves.toMatchObject({
      apiUrl: "http://localhost:8000",
      accessToken: "tok",
      installationId: "i-1",
    });
  });

  it("lee capacidades y borra credenciales", async () => {
    await ExtensionStorage.saveCredentials({ accessToken: "tok" });
    await ExtensionStorage.clearCredentials();
    await expect(ExtensionStorage.getCredentials()).resolves.toMatchObject({ accessToken: undefined });
    await expect(ExtensionStorage.getCapabilities()).resolves.toBeNull();
  });
});
