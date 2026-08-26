import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getDeliveries,
  getNotificationPreferences,
  getNotifications,
  getUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
  reactivateEmailDelivery,
  updateNotificationPreferences,
} from "../notificationService";

function stubFetch(body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function urlDe(fetchMock: ReturnType<typeof vi.fn>): string {
  return String(fetchMock.mock.calls[0][0]);
}

function initDe(fetchMock: ReturnType<typeof vi.fn>): RequestInit {
  return fetchMock.mock.calls[0][1] as RequestInit;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getNotifications", () => {
  it("pide el listado completo por defecto", async () => {
    const fetchMock = stubFetch([]);

    await getNotifications();

    expect(urlDe(fetchMock)).toMatch(/\/notifications$/);
  });

  it("filtra por no leídas cuando se le pide", async () => {
    const fetchMock = stubFetch([]);

    await getNotifications(true);

    expect(urlDe(fetchMock)).toContain("only_unread=true");
  });
});

describe("getUnreadCount", () => {
  it("devuelve el contador del backend", async () => {
    stubFetch({ count: 3 });

    await expect(getUnreadCount()).resolves.toEqual({ count: 3 });
  });
});

describe("markNotificationRead", () => {
  it("hace POST al aviso indicado", async () => {
    const fetchMock = stubFetch({ id: "n1" });

    await markNotificationRead("n1");

    expect(urlDe(fetchMock)).toMatch(/\/notifications\/n1\/read$/);
    expect(initDe(fetchMock).method).toBe("POST");
  });

  it("escapa el identificador en la ruta", async () => {
    const fetchMock = stubFetch({ id: "x" });

    await markNotificationRead("a/b");

    expect(urlDe(fetchMock)).toContain("a%2Fb");
  });
});

describe("markAllNotificationsRead", () => {
  it("hace POST a la ruta de marcar todo", async () => {
    const fetchMock = stubFetch({ updated: 2 });

    await markAllNotificationsRead();

    expect(urlDe(fetchMock)).toMatch(/\/notifications\/read-all$/);
    expect(initDe(fetchMock).method).toBe("POST");
  });
});

describe("preferencias", () => {
  it("lee las preferencias", async () => {
    const fetchMock = stubFetch({ enabled: true, threshold_pct: 70 });

    await getNotificationPreferences();

    expect(urlDe(fetchMock)).toMatch(/\/notifications\/preferences$/);
  });

  it("envía el umbral en porcentaje con PATCH", async () => {
    const fetchMock = stubFetch({ enabled: true, threshold_pct: 55 });

    await updateNotificationPreferences({ threshold_pct: 55 });

    const init = initDe(fetchMock);
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ threshold_pct: 55 });
  });

  it("envía el modo de entrega elegido", async () => {
    const fetchMock = stubFetch({ delivery_mode: "daily_digest" });

    await updateNotificationPreferences({ delivery_mode: "daily_digest" });

    expect(JSON.parse(String(initDe(fetchMock).body))).toEqual({
      delivery_mode: "daily_digest",
    });
  });

  it("reactiva el envío de correos con POST", async () => {
    const fetchMock = stubFetch({ email_delivery_enabled: true });

    await reactivateEmailDelivery();

    expect(urlDe(fetchMock)).toMatch(
      /\/notifications\/preferences\/reactivate-email$/,
    );
    expect(initDe(fetchMock).method).toBe("POST");
  });
});

describe("getDeliveries", () => {
  it("pide la bandeja de salida", async () => {
    const fetchMock = stubFetch([]);

    await getDeliveries();

    expect(urlDe(fetchMock)).toMatch(/\/notifications\/deliveries$/);
  });
});
