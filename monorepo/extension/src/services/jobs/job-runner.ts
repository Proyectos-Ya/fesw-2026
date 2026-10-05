import { Capabilities, ExtensionJob } from "../../types/schemas";
import { ExtensionStorage } from "../storage/extension-storage";

export class JobRunner {
  private isRunning: boolean = false;

  public async runCycle(capabilities: Capabilities): Promise<void> {
    if (!capabilities.fetch_jobs_enabled || this.isRunning) return;

    // Verificar inactividad del navegador
    const isIdle = await this.checkIfIdle(120);
    if (!isIdle) return;

    this.isRunning = true;
    try {
      const job = await this.leaseJob();
      if (!job) return;

      await this.processJob(job);
    } catch (err) {
      console.error("[JobRunner] Error en ciclo distribuido:", err);
    } finally {
      this.isRunning = false;
    }
  }

  private async checkIfIdle(thresholdSeconds: number): Promise<boolean> {
    if (typeof chrome === "undefined" || !chrome.idle?.queryState) {
      return true; // En tests o entornos sin chrome.idle
    }
    return new Promise((resolve) => {
      chrome.idle.queryState(thresholdSeconds, (state) => {
        resolve(state === "idle" || state === "locked");
      });
    });
  }

  public async leaseJob(): Promise<ExtensionJob | null> {
    const creds = await ExtensionStorage.getCredentials();
    if (!creds.apiUrl || !creds.installationId) return null;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (creds.accessToken) {
      headers.Authorization = `Bearer ${creds.accessToken}`;
    }

    const res = await fetch(`${creds.apiUrl}/extension/jobs/lease`, {
      method: "POST",
      headers,
      body: JSON.stringify({ installation_id: creds.installationId }),
    });

    if (res.status === 204 || !res.ok) return null;
    return (await res.json()) as ExtensionJob;
  }

  public async processJob(job: ExtensionJob): Promise<void> {
    const creds = await ExtensionStorage.getCredentials();
    if (!creds.apiUrl || !creds.installationId) return;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (creds.accessToken) {
      headers.Authorization = `Bearer ${creds.accessToken}`;
    }

    try {
      // Reportar resultado completado
      await fetch(`${creds.apiUrl}/extension/jobs/${job.job_id}/result`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          installation_id: creds.installationId,
          status: "completed",
          result_summary: {
            tender_code: job.tender_code,
            processed_at: new Date().toISOString(),
          },
        }),
      });
    } catch (error) {
      await fetch(`${creds.apiUrl}/extension/jobs/${job.job_id}/result`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          installation_id: creds.installationId,
          status: "failed",
          error_code: "network_error",
          error_detail: String(error),
        }),
      });
    }
  }
}
