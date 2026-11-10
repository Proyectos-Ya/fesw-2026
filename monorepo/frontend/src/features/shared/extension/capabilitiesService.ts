import { apiFetch } from "@/features/shared/api/client";

export interface ExtensionCapabilities {
  enabled: boolean;
  min_version: string;
  latest_version: string;
  mp_adapter_enabled: boolean;
  fetch_jobs_enabled: boolean;
  postulation_enabled: boolean;
  max_daily_fetches: number;
  polling_interval_seconds: number;
  supported_mp_hosts: string[];
  message: string | null;
}

export function getExtensionCapabilities(): Promise<ExtensionCapabilities> {
  return apiFetch<ExtensionCapabilities>("/extension/capabilities");
}
