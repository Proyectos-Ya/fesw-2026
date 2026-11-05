import { describe, expect, it, vi } from "vitest";
import { ContentScriptBridge } from "../content-script-bridge";

describe("ContentScriptBridge", () => {
  const defaultOrigin = "http://localhost:3000";

  it("rechaza origen desconocido o malicioso", () => {
    const postMessage = vi.fn();
    const sendRuntime = vi.fn();
    const bridge = new ContentScriptBridge({
      currentOrigin: defaultOrigin,
      extensionVersion: "0.1.0",
      postMessageToWindow: postMessage,
      sendMessageToRuntime: sendRuntime,
    });

    const handled = bridge.handleWindowMessage({
      origin: "https://malicious-site.com",
      data: { target: "CHIRIPA_EXTENSION", type: "PING" },
    });

    expect(handled).toBe(false);
    expect(postMessage).not.toHaveBeenCalled();
    expect(sendRuntime).not.toHaveBeenCalled();
  });

  it("responde PONG con nonce, versión y el estado real de vinculación", () => {
    const postMessage = vi.fn();
    const sendRuntime = vi.fn((_msg: unknown, cb?: (r: unknown) => void) => cb?.({ paired: true }));
    const bridge = new ContentScriptBridge({
      currentOrigin: defaultOrigin,
      extensionVersion: "0.2.0",
      postMessageToWindow: postMessage,
      sendMessageToRuntime: sendRuntime,
    });

    const handled = bridge.handleWindowMessage({
      origin: defaultOrigin,
      data: { target: "CHIRIPA_EXTENSION", type: "PING", nonce: "test-nonce-123" },
    });

    expect(handled).toBe(true);
    expect(sendRuntime).toHaveBeenCalledWith({ action: "GET_STATUS" }, expect.any(Function));
    expect(postMessage).toHaveBeenCalledWith(
      {
        target: "CHIRIPA_WEB",
        type: "PONG",
        nonce: "test-nonce-123",
        version: "0.2.0",
        features: ["postulation"],
        mp_access: true,
        paired: true,
      },
      defaultOrigin
    );
  });

  it("responde PONG con paired=false si el service worker no contesta", () => {
    const postMessage = vi.fn();
    const sendRuntime = vi.fn((_msg: unknown, cb?: (r: unknown) => void) => cb?.(undefined));
    const bridge = new ContentScriptBridge({
      currentOrigin: defaultOrigin,
      extensionVersion: "0.2.0",
      postMessageToWindow: postMessage,
      sendMessageToRuntime: sendRuntime,
    });
    bridge.handleWindowMessage({
      origin: defaultOrigin,
      data: { target: "CHIRIPA_EXTENSION", type: "PING", nonce: "n" },
    });
    expect(postMessage).toHaveBeenCalledWith(expect.objectContaining({ type: "PONG", paired: false }), defaultOrigin);
  });

  it("rechaza mensaje de pairing expirado (> 60 segundos)", () => {
    const postMessage = vi.fn();
    const sendRuntime = vi.fn();
    const bridge = new ContentScriptBridge({
      currentOrigin: defaultOrigin,
      extensionVersion: "0.1.0",
      postMessageToWindow: postMessage,
      sendMessageToRuntime: sendRuntime,
    });

    const expiredTimestamp = Date.now() - 65_000;
    const handled = bridge.handleWindowMessage({
      origin: defaultOrigin,
      data: {
        target: "CHIRIPA_EXTENSION",
        type: "PAIR_SESSION",
        nonce: "d3b07384-d113-4f9e-b248-b4b732560e90",
        payload: {
          pairing_ticket: "TKT-12345",
          api_url: "http://localhost:8000",
          access_token: "token-abc",
          timestamp: expiredTimestamp,
        },
      },
    });

    expect(handled).toBe(false);
    expect(sendRuntime).not.toHaveBeenCalled();
  });

  it("acepta y reenvía pairing válido al background script", () => {
    const postMessage = vi.fn();
    const sendRuntime = vi.fn((_msg, cb) => {
      cb({ success: true, installation_id: "inst-999" });
    });
    const bridge = new ContentScriptBridge({
      currentOrigin: defaultOrigin,
      extensionVersion: "0.1.0",
      postMessageToWindow: postMessage,
      sendMessageToRuntime: sendRuntime,
    });

    const handled = bridge.handleWindowMessage({
      origin: defaultOrigin,
      data: {
        target: "CHIRIPA_EXTENSION",
        type: "PAIR_SESSION",
        nonce: "d3b07384-d113-4f9e-b248-b4b732560e90",
        payload: {
          pairing_ticket: "TKT-12345",
          api_url: "http://localhost:8000",
          access_token: "token-abc",
          timestamp: Date.now(),
        },
      },
    });

    expect(handled).toBe(true);
    expect(sendRuntime).toHaveBeenCalled();
    expect(postMessage).toHaveBeenCalledWith(
      {
        target: "CHIRIPA_WEB",
        type: "PAIR_SUCCESS",
        nonce: "d3b07384-d113-4f9e-b248-b4b732560e90",
        installation_id: "inst-999",
      },
      defaultOrigin
    );
  });

  it("procesa OPEN_POSTULATION y responde con tab_id", () => {
    const postMessage = vi.fn();
    const sendRuntime = vi.fn((_msg, cb) => {
      cb({ ok: true, tab_id: 42 });
    });
    const bridge = new ContentScriptBridge({
      currentOrigin: defaultOrigin,
      extensionVersion: "0.2.0",
      postMessageToWindow: postMessage,
      sendMessageToRuntime: sendRuntime,
    });

    const nonce = "e7b07384-d113-4f9e-b248-b4b732560e91";
    const handled = bridge.handleWindowMessage({
      origin: defaultOrigin,
      data: {
        target: "CHIRIPA_EXTENSION",
        type: "OPEN_POSTULATION",
        nonce,
        payload: {
          tender_code: "2499-12-L126",
          mp_url: "https://www.mercadopublico.cl/ficha.html?code=2499-12-L126",
        },
      },
    });

    expect(handled).toBe(true);
    expect(sendRuntime).toHaveBeenCalledWith(
      {
        action: "OPEN_POSTULATION",
        payload: {
          tender_code: "2499-12-L126",
          mp_url: "https://www.mercadopublico.cl/ficha.html?code=2499-12-L126",
        },
      },
      expect.any(Function)
    );
    expect(postMessage).toHaveBeenCalledWith(
      {
        target: "CHIRIPA_WEB",
        type: "POSTULATION_TAB_OPENED",
        nonce,
        tab_id: 42,
        ok: true,
      },
      defaultOrigin
    );
  });

  it("procesa CONFIRM_POSTULATION y responde con ACK", () => {
    const postMessage = vi.fn();
    const sendRuntime = vi.fn((_msg, cb) => {
      cb({ ok: true });
    });
    const bridge = new ContentScriptBridge({
      currentOrigin: defaultOrigin,
      extensionVersion: "0.2.0",
      postMessageToWindow: postMessage,
      sendMessageToRuntime: sendRuntime,
    });

    const nonce = "f8c07384-d113-4f9e-b248-b4b732560e92";
    const payload = {
      tender_code: "2499-12-L126",
      company_rut: "76.086.428-5",
      company_name: "Test Ltda",
      items: [
        {
          line_number: 1,
          name: "Item 1",
          quantity: 1,
          unit_price: 1500,
          total_price: 1500,
        },
      ],
      total_clp: 1500,
      observations: "Detalle",
      validity_days: 30,
      delivery_term_days: 10,
      files: [],
    };

    const handled = bridge.handleWindowMessage({
      origin: defaultOrigin,
      data: {
        target: "CHIRIPA_EXTENSION",
        type: "CONFIRM_POSTULATION",
        nonce,
        payload,
      },
    });

    expect(handled).toBe(true);
    expect(sendRuntime).toHaveBeenCalledWith(
      {
        action: "CONFIRM_POSTULATION",
        payload,
      },
      expect.any(Function)
    );
    expect(postMessage).toHaveBeenCalledWith(
      {
        target: "CHIRIPA_WEB",
        type: "CONFIRM_POSTULATION_ACK",
        nonce,
        tender_code: "2499-12-L126",
        ok: true,
      },
      defaultOrigin
    );
  });

  it("procesa FOCUS_POSTULATION_TAB", () => {
    const postMessage = vi.fn();
    const sendRuntime = vi.fn((_msg, cb) => {
      cb({ ok: true });
    });
    const bridge = new ContentScriptBridge({
      currentOrigin: defaultOrigin,
      extensionVersion: "0.2.0",
      postMessageToWindow: postMessage,
      sendMessageToRuntime: sendRuntime,
    });

    const nonce = "a1b2c3d4-d113-4f9e-b248-b4b732560e93";
    const handled = bridge.handleWindowMessage({
      origin: defaultOrigin,
      data: {
        target: "CHIRIPA_EXTENSION",
        type: "FOCUS_POSTULATION_TAB",
        nonce,
        payload: { tender_code: "2499-12-L126" },
      },
    });

    expect(handled).toBe(true);
    expect(sendRuntime).toHaveBeenCalledWith(
      {
        action: "FOCUS_POSTULATION_TAB",
        payload: { tender_code: "2499-12-L126" },
      },
      expect.any(Function)
    );
    expect(postMessage).toHaveBeenCalledWith(
      {
        target: "CHIRIPA_WEB",
        type: "FOCUS_POSTULATION_TAB_ACK",
        nonce,
        ok: true,
      },
      defaultOrigin
    );
  });

  describe("validaciones de seguridad", () => {
    const makeBridge = () => {
      const postMessage = vi.fn();
      const sendRuntime = vi.fn();
      const bridge = new ContentScriptBridge({
        currentOrigin: defaultOrigin,
        extensionVersion: "0.2.0",
        postMessageToWindow: postMessage,
        sendMessageToRuntime: sendRuntime,
      });
      return { bridge, postMessage, sendRuntime };
    };

    it("rechaza mensajes sin origen", () => {
      const { bridge, postMessage, sendRuntime } = makeBridge();
      const handled = bridge.handleWindowMessage({
        origin: "",
        data: { target: "CHIRIPA_EXTENSION", type: "PING", nonce: "n" },
      });
      expect(handled).toBe(false);
      expect(postMessage).not.toHaveBeenCalled();
      expect(sendRuntime).not.toHaveBeenCalled();
    });

    it("rechaza OPEN_POSTULATION con mp_url fuera de mercadopublico.cl", () => {
      const { bridge, sendRuntime } = makeBridge();
      for (const mp_url of [
        "https://evil.example/resumen-cotizacion/1-1-COT26",
        "https://mercadopublico.cl.evil.example/x",
        "javascript:alert(1)",
        "http://compra-agil.mercadopublico.cl/resumen-cotizacion/1-1-COT26",
      ]) {
        const handled = bridge.handleWindowMessage({
          origin: defaultOrigin,
          data: {
            target: "CHIRIPA_EXTENSION",
            type: "OPEN_POSTULATION",
            nonce: "d3b07384-d113-4f9e-b248-b4b732560e90",
            payload: { tender_code: "1-1-COT26", mp_url },
          },
        });
        expect(handled, mp_url).toBe(false);
      }
      expect(sendRuntime).not.toHaveBeenCalled();
    });

    it("acepta OPEN_POSTULATION con mp_url https de un subdominio de mercadopublico.cl", () => {
      const { bridge, sendRuntime } = makeBridge();
      const handled = bridge.handleWindowMessage({
        origin: defaultOrigin,
        data: {
          target: "CHIRIPA_EXTENSION",
          type: "OPEN_POSTULATION",
          nonce: "d3b07384-d113-4f9e-b248-b4b732560e90",
          payload: {
            tender_code: "1-1-COT26",
            mp_url: "https://compra-agil.mercadopublico.cl/resumen-cotizacion/1-1-COT26",
          },
        },
      });
      expect(handled).toBe(true);
      expect(sendRuntime).toHaveBeenCalledTimes(1);
    });

    it("rechaza PAIR_SESSION con api_url sin https fuera de localhost", () => {
      const { bridge, sendRuntime } = makeBridge();
      const handled = bridge.handleWindowMessage({
        origin: defaultOrigin,
        data: {
          target: "CHIRIPA_EXTENSION",
          type: "PAIR_SESSION",
          nonce: "d3b07384-d113-4f9e-b248-b4b732560e90",
          payload: {
            pairing_ticket: "TKT-1",
            api_url: "http://attacker.example",
            access_token: "token",
            timestamp: Date.now(),
          },
        },
      });
      expect(handled).toBe(false);
      expect(sendRuntime).not.toHaveBeenCalled();
    });
  });
});
