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

  it("responde PONG con nonce y versión ante PING", () => {
    const postMessage = vi.fn();
    const sendRuntime = vi.fn();
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
        type: "PING",
        nonce: "test-nonce-123",
      },
    });

    expect(handled).toBe(true);
    expect(postMessage).toHaveBeenCalledWith(
      {
        target: "CHIRIPA_WEB",
        type: "PONG",
        nonce: "test-nonce-123",
        version: "0.1.0",
      },
      defaultOrigin
    );
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
});
