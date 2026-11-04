/**
 * Protocolo de comunicación Web <-> Extensión de Chiripa.
 * No utiliza `any` y valida orígenes y nonces estrictamente.
 */

export interface PostulationFilePayload {
  name: string;
  type: string;
  size: number;
  data_base64: string;
}

export interface PostulationItemPayload {
  line_number: number;
  product_code?: string | null;
  name: string;
  quantity: number;
  unit?: string;
  unit_price: number;
  total_price: number;
  technical_spec?: string | null;
}

export interface PostulationConfirmPayload {
  tender_code: string;
  tender_title?: string;
  company_rut: string;
  company_name: string;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  items: PostulationItemPayload[];
  total_clp: number;
  observations: string;
  validity_days: number;
  delivery_term_days: number;
  files: PostulationFilePayload[];
}

export interface ProbeExtensionResult {
  installed: boolean;
  version?: string;
  postulation_enabled?: boolean;
  mp_access?: boolean;
}

interface BridgeIncomingMessage {
  target?: string;
  type?: string;
  nonce?: string;
  version?: string;
  features?: string[];
  mp_access?: boolean;
  tab_id?: number;
  tender_code?: string;
  ok?: boolean;
  error?: string;
}

function isSameOrigin(origin: string): boolean {
  if (typeof window === "undefined") return false;
  return origin === window.location.origin;
}

/**
 * Sondea si la extensión de Chiripa está instalada y activa.
 */
export async function probeExtension(timeoutMs: number = 1200): Promise<ProbeExtensionResult> {
  if (typeof window === "undefined") {
    return { installed: false };
  }

  const nonce = crypto.randomUUID();

  return new Promise<ProbeExtensionResult>((resolve) => {
    let timer: ReturnType<typeof setTimeout> | null = null;

    const handleMessage = (event: MessageEvent<unknown>) => {
      if (!isSameOrigin(event.origin)) return;
      const data = event.data as BridgeIncomingMessage | null | undefined;
      if (!data || data.target !== "CHIRIPA_WEB") return;

      if (data.type === "PONG") {
        if (timer) clearTimeout(timer);
        window.removeEventListener("message", handleMessage);

        const hasPostulation = Array.isArray(data.features) && data.features.includes("postulation");
        resolve({
          installed: true,
          version: data.version,
          postulation_enabled: hasPostulation,
          mp_access: data.mp_access,
        });
      }
    };

    window.addEventListener("message", handleMessage);

    window.postMessage(
      {
        target: "CHIRIPA_EXTENSION",
        type: "PING",
        nonce,
      },
      window.location.origin
    );

    timer = setTimeout(() => {
      window.removeEventListener("message", handleMessage);
      resolve({ installed: false });
    }, timeoutMs);
  });
}

/**
 * CA3: Envía comando para abrir la pestaña de Mercado Público en segundo plano (inactiva).
 */
export async function openPostulationTab(
  tenderCode: string,
  mpUrl?: string,
  timeoutMs: number = 3000
): Promise<{ ok: boolean; tab_id?: number; error?: string }> {
  if (typeof window === "undefined") {
    return { ok: false, error: "Window undefined" };
  }

  const nonce = crypto.randomUUID();

  return new Promise((resolve) => {
    let timer: ReturnType<typeof setTimeout> | null = null;

    const handleMessage = (event: MessageEvent<unknown>) => {
      if (!isSameOrigin(event.origin)) return;
      const data = event.data as BridgeIncomingMessage | null | undefined;
      if (!data || data.target !== "CHIRIPA_WEB") return;

      if (data.type === "POSTULATION_TAB_OPENED" && data.nonce === nonce) {
        if (timer) clearTimeout(timer);
        window.removeEventListener("message", handleMessage);
        resolve({
          ok: data.ok ?? false,
          tab_id: data.tab_id,
          error: data.error,
        });
      }
    };

    window.addEventListener("message", handleMessage);

    window.postMessage(
      {
        target: "CHIRIPA_EXTENSION",
        type: "OPEN_POSTULATION",
        nonce,
        payload: {
          tender_code: tenderCode,
          mp_url: mpUrl,
        },
      },
      window.location.origin
    );

    timer = setTimeout(() => {
      window.removeEventListener("message", handleMessage);
      resolve({ ok: false, error: "Timeout waiting for postulation tab opening" });
    }, timeoutMs);
  });
}

/**
 * CA4: Envía el paquete de postulación confirmado a la extensión.
 */
export async function confirmPostulation(
  payload: PostulationConfirmPayload,
  timeoutMs: number = 5000
): Promise<{ ok: boolean; error?: string }> {
  if (typeof window === "undefined") {
    return { ok: false, error: "Window undefined" };
  }

  const nonce = crypto.randomUUID();

  return new Promise((resolve) => {
    let timer: ReturnType<typeof setTimeout> | null = null;

    const handleMessage = (event: MessageEvent<unknown>) => {
      if (!isSameOrigin(event.origin)) return;
      const data = event.data as BridgeIncomingMessage | null | undefined;
      if (!data || data.target !== "CHIRIPA_WEB") return;

      if (data.type === "CONFIRM_POSTULATION_ACK" && data.nonce === nonce) {
        if (timer) clearTimeout(timer);
        window.removeEventListener("message", handleMessage);
        resolve({
          ok: data.ok ?? false,
          error: data.error,
        });
      }
    };

    window.addEventListener("message", handleMessage);

    window.postMessage(
      {
        target: "CHIRIPA_EXTENSION",
        type: "CONFIRM_POSTULATION",
        nonce,
        payload,
      },
      window.location.origin
    );

    timer = setTimeout(() => {
      window.removeEventListener("message", handleMessage);
      resolve({ ok: false, error: "Timeout confirming postulation" });
    }, timeoutMs);
  });
}

/**
 * Enfoca la pestaña de postulación de Mercado Público ya abierta.
 */
export async function focusPostulationTab(
  tenderCode: string,
  timeoutMs: number = 2000
): Promise<{ ok: boolean; error?: string }> {
  if (typeof window === "undefined") {
    return { ok: false, error: "Window undefined" };
  }

  const nonce = crypto.randomUUID();

  return new Promise((resolve) => {
    let timer: ReturnType<typeof setTimeout> | null = null;

    const handleMessage = (event: MessageEvent<unknown>) => {
      if (!isSameOrigin(event.origin)) return;
      const data = event.data as BridgeIncomingMessage | null | undefined;
      if (!data || data.target !== "CHIRIPA_WEB") return;

      if (data.type === "FOCUS_POSTULATION_TAB_ACK" && data.nonce === nonce) {
        if (timer) clearTimeout(timer);
        window.removeEventListener("message", handleMessage);
        resolve({
          ok: data.ok ?? false,
          error: data.error,
        });
      }
    };

    window.addEventListener("message", handleMessage);

    window.postMessage(
      {
        target: "CHIRIPA_EXTENSION",
        type: "FOCUS_POSTULATION_TAB",
        nonce,
        payload: { tender_code: tenderCode },
      },
      window.location.origin
    );

    timer = setTimeout(() => {
      window.removeEventListener("message", handleMessage);
      resolve({ ok: false, error: "Timeout focusing postulation tab" });
    }, timeoutMs);
  });
}
