import {
  BridgeConfirmPostulationMessageSchema,
  BridgeFocusTabMessageSchema,
  BridgeOpenPostulationMessageSchema,
  BridgePairingMessageSchema,
} from "../../types/schemas";

export interface BridgeConfig {
  currentOrigin: string;
  extensionVersion: string;
  sendMessageToRuntime: (
    message: unknown,
    responseCallback?: (response: unknown) => void
  ) => void;
  postMessageToWindow: (message: unknown, targetOrigin: string) => void;
}

export class ContentScriptBridge {
  private config: BridgeConfig;

  constructor(config: BridgeConfig) {
    this.config = config;
  }

  public handleWindowMessage(event: {
    origin: string;
    data: Record<string, unknown>;
  }): boolean {
    // 1. Origen estricto: debe coincidir exactamente con el origen actual
    if (event.origin !== this.config.currentOrigin) {
      return false;
    }

    const data = event.data;
    if (!data || data.target !== "CHIRIPA_EXTENSION") {
      return false;
    }

    // 2. Protocolo Handshake PING -> PONG
    if (data.type === "PING") {
      this.config.postMessageToWindow(
        {
          target: "CHIRIPA_WEB",
          type: "PONG",
          nonce: data.nonce,
          version: this.config.extensionVersion,
          features: ["postulation"],
          mp_access: true,
        },
        this.config.currentOrigin
      );
      return true;
    }

    // 3. Emparejamiento de sesión
    if (data.type === "PAIR_SESSION") {
      const parsed = BridgePairingMessageSchema.safeParse(data);
      if (!parsed.success) {
        return false;
      }

      // TTL estricto de 60 segundos
      const now = Date.now();
      if (Math.abs(now - parsed.data.payload.timestamp) > 60_000) {
        return false;
      }

      this.config.sendMessageToRuntime(
        { action: "STORE_PAIRING", payload: parsed.data.payload },
        (response: unknown) => {
          const resp = response as { success?: boolean; installation_id?: string } | undefined;
          if (resp?.success) {
            this.config.postMessageToWindow(
              {
                target: "CHIRIPA_WEB",
                type: "PAIR_SUCCESS",
                nonce: parsed.data.nonce,
                installation_id: resp.installation_id,
              },
              this.config.currentOrigin
            );
          }
        }
      );
      return true;
    }

    // 4. Apertura de pestaña de Mercado Público para postulación (HU-032 / CA3)
    if (data.type === "OPEN_POSTULATION") {
      const parsed = BridgeOpenPostulationMessageSchema.safeParse(data);
      if (!parsed.success) {
        return false;
      }

      this.config.sendMessageToRuntime(
        { action: "OPEN_POSTULATION", payload: parsed.data.payload },
        (response: unknown) => {
          const resp = response as { ok?: boolean; tab_id?: number; error?: string } | undefined;
          this.config.postMessageToWindow(
            {
              target: "CHIRIPA_WEB",
              type: "POSTULATION_TAB_OPENED",
              nonce: parsed.data.nonce,
              tab_id: resp?.tab_id,
              ok: resp?.ok ?? false,
              error: resp?.error,
            },
            this.config.currentOrigin
          );
        }
      );
      return true;
    }

    // 5. Confirmación y carga de paquete de postulación (HU-032 / CA4)
    if (data.type === "CONFIRM_POSTULATION") {
      const parsed = BridgeConfirmPostulationMessageSchema.safeParse(data);
      if (!parsed.success) {
        return false;
      }

      this.config.sendMessageToRuntime(
        { action: "CONFIRM_POSTULATION", payload: parsed.data.payload },
        (response: unknown) => {
          const resp = response as { ok?: boolean; error?: string } | undefined;
          this.config.postMessageToWindow(
            {
              target: "CHIRIPA_WEB",
              type: "CONFIRM_POSTULATION_ACK",
              nonce: parsed.data.nonce,
              tender_code: parsed.data.payload.tender_code,
              ok: resp?.ok ?? false,
              error: resp?.error,
            },
            this.config.currentOrigin
          );
        }
      );
      return true;
    }

    // 6. Enfocar pestaña de postulación
    if (data.type === "FOCUS_POSTULATION_TAB") {
      const parsed = BridgeFocusTabMessageSchema.safeParse(data);
      if (!parsed.success) {
        return false;
      }

      this.config.sendMessageToRuntime(
        { action: "FOCUS_POSTULATION_TAB", payload: parsed.data.payload },
        (response: unknown) => {
          const resp = response as { ok?: boolean; error?: string } | undefined;
          this.config.postMessageToWindow(
            {
              target: "CHIRIPA_WEB",
              type: "FOCUS_POSTULATION_TAB_ACK",
              nonce: parsed.data.nonce,
              ok: resp?.ok ?? false,
              error: resp?.error,
            },
            this.config.currentOrigin
          );
        }
      );
      return true;
    }

    return false;
  }
}
