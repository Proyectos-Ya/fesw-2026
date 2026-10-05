import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { ExtensionPairingSection } from "../ExtensionPairingSection";
import * as apiClientModule from "@/features/shared/api/client";
import * as supabaseClientModule from "@/features/auth/supabase/client";

vi.mock("@/features/shared/api/client", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("@/features/auth/supabase/client", () => ({
  crearClienteNavegador: vi.fn(),
}));

describe("ExtensionPairingSection", () => {
  const supplierId = "sup-test-123";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renderiza el estado inicial con el botón de vinculación", () => {
    render(<ExtensionPairingSection supplierId={supplierId} />);

    expect(screen.getByText("Extensión de Navegador")).toBeInTheDocument();
    expect(screen.getByText("Vincular en este navegador")).toBeInTheDocument();
  });

  it("muestra estado de extensión no detectada si no hay respuesta PONG", async () => {
    vi.useFakeTimers();
    render(<ExtensionPairingSection supplierId={supplierId} />);

    const button = screen.getByText("Vincular en este navegador");
    fireEvent.click(button);

    expect(screen.getByText("Detectando extensión en tu navegador...")).toBeInTheDocument();

    // Avanzar temporizador dentro de act
    act(() => {
      vi.advanceTimersByTime(1600);
    });

    expect(
      screen.getByText("No detectamos la extensión activa en este navegador.")
    ).toBeInTheDocument();
  });

  it("completa emparejamiento cuando la extensión responde PONG y PAIR_SUCCESS", async () => {
    vi.useRealTimers();
    vi.mocked(apiClientModule.apiFetch).mockResolvedValueOnce({
      pairing_ticket: "TKT-12345",
      expires_in_seconds: 300,
    });

    const mockGetSession = vi.fn().mockResolvedValue({
      data: {
        session: {
          access_token: "jwt-token-123",
          refresh_token: "refresh-token-123",
        },
      },
    });

    vi.mocked(supabaseClientModule.crearClienteNavegador).mockReturnValue({
      auth: {
        getSession: mockGetSession,
      },
    } as unknown as ReturnType<typeof supabaseClientModule.crearClienteNavegador>);

    // Mock de window.postMessage para simular la extensión respondiendo
    const originalPostMessage = window.postMessage;
    window.postMessage = vi.fn((message, _targetOrigin) => {
      queueMicrotask(() => {
        if (message?.target === "CHIRIPA_EXTENSION" && message.type === "PING") {
          window.dispatchEvent(
            new MessageEvent("message", {
              data: {
                target: "CHIRIPA_WEB",
                type: "PONG",
                nonce: message.nonce,
                version: "0.1.0",
              },
            })
          );
        } else if (message?.target === "CHIRIPA_EXTENSION" && message.type === "PAIR_SESSION") {
          window.dispatchEvent(
            new MessageEvent("message", {
              data: {
                target: "CHIRIPA_WEB",
                type: "PAIR_SUCCESS",
                nonce: message.nonce,
                installation_id: "inst-123",
              },
            })
          );
        }
      });
    });

    try {
      render(<ExtensionPairingSection supplierId={supplierId} />);

      const button = screen.getByText("Vincular en este navegador");
      fireEvent.click(button);

      await waitFor(
        () => {
          expect(
            screen.getByText("¡Extensión vinculada y lista para sincronizar anexos!")
          ).toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      expect(apiClientModule.apiFetch).toHaveBeenCalledWith(
        "/extension/pairing/start",
        expect.objectContaining({
          method: "POST",
        })
      );
    } finally {
      window.postMessage = originalPostMessage;
    }
  });
});
