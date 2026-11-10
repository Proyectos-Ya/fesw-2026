import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClientModule from "@/features/shared/api/client";
import * as supabaseClientModule from "@/features/auth/supabase/client";
import { pairExtension, probeExtension } from "../extensionBridge";

vi.mock("@/features/shared/api/client", () => ({ apiFetch: vi.fn() }));
vi.mock("@/features/auth/supabase/client", () => ({ crearClienteNavegador: vi.fn() }));

const mockSession = (token: string | null) =>
  vi.mocked(supabaseClientModule.crearClienteNavegador).mockReturnValue({
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: token ? { access_token: token, refresh_token: "refresh-secreto" } : null },
      }),
    },
  } as unknown as ReturnType<typeof supabaseClientModule.crearClienteNavegador>);

/** Responde como la extensión a PAIR_SESSION; devuelve los mensajes recibidos. */
const fakeExtension = (reply: boolean) => {
  const received: Record<string, unknown>[] = [];
  const listener = (event: MessageEvent) => {
    const data = event.data;
    if (data?.target === "CHIRIPA_EXTENSION" && data.type === "PAIR_SESSION") {
      received.push(data);
      if (reply) {
        window.dispatchEvent(
          new MessageEvent("message", {
            origin: window.location.origin,
            data: { target: "CHIRIPA_WEB", type: "PAIR_SUCCESS", nonce: data.nonce, installation_id: "i-1" },
          })
        );
      }
    }
  };
  window.addEventListener("message", listener);
  return { received, stop: () => window.removeEventListener("message", listener) };
};

describe("pairExtension", () => {
  beforeEach(() => {
    vi.mocked(apiClientModule.apiFetch).mockResolvedValue({ pairing_ticket: "TKT-1", expires_in_seconds: 60 });
  });

  it("solo confirma la vinculación cuando la extensión responde PAIR_SUCCESS", async () => {
    mockSession("token-1");
    const ext = fakeExtension(true);
    await expect(pairExtension({ workspaceId: null, timeoutMs: 500 })).resolves.toEqual({ ok: true });
    ext.stop();
  });

  it("no da por vinculada la extensión si no confirma a tiempo", async () => {
    mockSession("token-1");
    const ext = fakeExtension(false);
    const res = await pairExtension({ workspaceId: null, timeoutMs: 100 });
    expect(res.ok).toBe(false);
    ext.stop();
  });

  it("no envía el refresh token de la sesión a la extensión", async () => {
    mockSession("token-1");
    const ext = fakeExtension(true);
    await pairExtension({ workspaceId: null, timeoutMs: 500 });
    const payload = ext.received[0].payload as Record<string, unknown>;
    expect(payload.access_token).toBe("token-1");
    expect(payload).not.toHaveProperty("refresh_token");
    ext.stop();
  });

  it("falla sin sesión activa y no contacta a la extensión", async () => {
    mockSession(null);
    const ext = fakeExtension(true);
    const res = await pairExtension({ workspaceId: null, timeoutMs: 100 });
    expect(res.ok).toBe(false);
    expect(ext.received).toHaveLength(0);
    ext.stop();
  });
});

describe("probeExtension: estado de vinculación", () => {
  it("expone paired según lo que informa la extensión", async () => {
    const promise = probeExtension(500);
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: window.location.origin,
        data: { target: "CHIRIPA_WEB", type: "PONG", version: "0.2.0", features: ["postulation"], paired: true },
      })
    );
    await expect(promise).resolves.toMatchObject({ installed: true, paired: true });
  });
});
