import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  confirmPostulation,
  focusPostulationTab,
  openPostulationTab,
  probeExtension,
} from "../extensionBridge";

describe("extensionBridge", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("probeExtension devuelve installed=true si la extensión responde PONG a tiempo", async () => {
    const messagePromise = probeExtension(500);

    // Simular que la extensión responde al mensaje PING
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: window.location.origin,
        data: {
          target: "CHIRIPA_WEB",
          type: "PONG",
          version: "0.2.0",
          features: ["postulation"],
        },
      })
    );

    const result = await messagePromise;
    expect(result.installed).toBe(true);
    expect(result.version).toBe("0.2.0");
    expect(result.postulation_enabled).toBe(true);
  });

  it("probeExtension devuelve installed=false si se agota el timeout", async () => {
    const result = await probeExtension(100);
    expect(result.installed).toBe(false);
    expect(result.version).toBeUndefined();
  });

  it("openPostulationTab envía OPEN_POSTULATION y resuelve con el tab_id devuelto", async () => {
    let capturedNonce = "";
    const listener = (event: MessageEvent) => {
      const data = event.data;
      if (data?.target === "CHIRIPA_EXTENSION" && data.type === "OPEN_POSTULATION") {
        capturedNonce = data.nonce;
        window.dispatchEvent(
          new MessageEvent("message", {
            origin: window.location.origin,
            data: {
              target: "CHIRIPA_WEB",
              type: "POSTULATION_TAB_OPENED",
              nonce: capturedNonce,
              tab_id: 101,
              ok: true,
            },
          })
        );
      }
    };
    window.addEventListener("message", listener);

    const res = await openPostulationTab("2499-12-L126", undefined, 500);
    expect(res.ok).toBe(true);
    expect(res.tab_id).toBe(101);

    window.removeEventListener("message", listener);
  });

  it("confirmPostulation envía CONFIRM_POSTULATION y resuelve ACK", async () => {
    let capturedNonce = "";
    const listener = (event: MessageEvent) => {
      const data = event.data;
      if (data?.target === "CHIRIPA_EXTENSION" && data.type === "CONFIRM_POSTULATION") {
        capturedNonce = data.nonce;
        window.dispatchEvent(
          new MessageEvent("message", {
            origin: window.location.origin,
            data: {
              target: "CHIRIPA_WEB",
              type: "CONFIRM_POSTULATION_ACK",
              nonce: capturedNonce,
              tender_code: "2499-12-L126",
              ok: true,
            },
          })
        );
      }
    };
    window.addEventListener("message", listener);

    const res = await confirmPostulation(
      {
        tender_code: "2499-12-L126",
        company_rut: "76.086.428-5",
        company_name: "Test SpA",
        items: [
          {
            line_number: 1,
            name: "Item",
            quantity: 1,
            unit_price: 100,
            total_price: 100,
          },
        ],
        total_clp: 100,
        observations: "Nota",
        validity_days: 30,
        delivery_term_days: 5,
        files: [],
      },
      500
    );

    expect(res.ok).toBe(true);
    window.removeEventListener("message", listener);
  });

  it("focusPostulationTab envía FOCUS_POSTULATION_TAB y resuelve ACK", async () => {
    let capturedNonce = "";
    const listener = (event: MessageEvent) => {
      const data = event.data;
      if (data?.target === "CHIRIPA_EXTENSION" && data.type === "FOCUS_POSTULATION_TAB") {
        capturedNonce = data.nonce;
        window.dispatchEvent(
          new MessageEvent("message", {
            origin: window.location.origin,
            data: {
              target: "CHIRIPA_WEB",
              type: "FOCUS_POSTULATION_TAB_ACK",
              nonce: capturedNonce,
              ok: true,
            },
          })
        );
      }
    };
    window.addEventListener("message", listener);

    const res = await focusPostulationTab("2499-12-L126", 500);
    expect(res.ok).toBe(true);
    window.removeEventListener("message", listener);
  });
});
