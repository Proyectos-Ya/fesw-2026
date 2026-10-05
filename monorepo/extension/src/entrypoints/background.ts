import { defineBackground } from "wxt/sandbox";
import { JobRunner } from "../services/jobs/job-runner";
import { ExtensionStorage } from "../services/storage/extension-storage";
import { Capabilities } from "../types/schemas";

export default defineBackground(() => {
  const jobRunner = new JobRunner();

  // Escuchar mensajes internos de Content Scripts o Popup
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.action === "STORE_PAIRING") {
      const payload = message.payload;
      (async () => {
        let installationId = (await ExtensionStorage.getCredentials()).installationId;
        if (!installationId) {
          installationId = crypto.randomUUID();
        }

        await ExtensionStorage.saveCredentials({
          apiUrl: payload.api_url,
          accessToken: payload.access_token,
          refreshToken: payload.refresh_token,
          workspaceId: payload.workspace_id,
          installationId,
        });

        // Confirmar la instalación ante el backend
        try {
          const res = await fetch(`${payload.api_url}/extension/pairing/confirm`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              pairing_ticket: payload.pairing_ticket,
              installation_id: installationId,
              browser: "chrome",
              extension_version: "0.1.0",
            }),
          });
          if (res.ok) {
            const data = await res.json();
            if (data.capabilities) {
              await ExtensionStorage.saveCapabilities(data.capabilities);
            }
          }
        } catch (e) {
          console.error("[Background] Error confirmando pairing:", e);
        }

        sendResponse({ success: true, installation_id: installationId });
      })();
      return true; // async sendResponse
    }

    if (message?.action === "GET_STATUS") {
      (async () => {
        const creds = await ExtensionStorage.getCredentials();
        const caps = await ExtensionStorage.getCapabilities();
        sendResponse({
          paired: Boolean(creds.accessToken),
          workspaceId: creds.workspaceId,
          capabilities: caps,
        });
      })();
      return true;
    }
  });

  // Configurar alarma periódica para sincronización y cola distribuida (cada 5 minutos)
  chrome.alarms.create("chiripa_sync_tick", { periodInMinutes: 5 });

  chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === "chiripa_sync_tick") {
      const creds = await ExtensionStorage.getCredentials();
      if (!creds.apiUrl || !creds.installationId) return;

      try {
        // 1. Latido y actualización de capacidades
        const res = await fetch(`${creds.apiUrl}/extension/installations/heartbeat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            installation_id: creds.installationId,
            extension_version: "0.1.0",
          }),
        });

        if (res.ok) {
          const data = (await res.json()) as { capabilities?: Capabilities };
          if (data.capabilities) {
            await ExtensionStorage.saveCapabilities(data.capabilities);
            // 2. Ejecutar ciclo distribuido
            await jobRunner.runCycle(data.capabilities);
          }
        }
      } catch (err) {
        console.error("[Background] Error en sync_tick:", err);
      }
    }
  });
});
