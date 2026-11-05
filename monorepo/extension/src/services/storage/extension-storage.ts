import { localGet, localRemove, localSet } from "./local-storage";
import { Capabilities } from "../../types/schemas";

export interface StoredCredentials {
  apiUrl?: string;
  accessToken?: string;
  refreshToken?: string;
  workspaceId?: string | null;
  installationId?: string;
}

export class ExtensionStorage {
  private static readonly KEY_API_URL = "chiripa_api_url";
  private static readonly KEY_ACCESS_TOKEN = "chiripa_access_token";
  private static readonly KEY_REFRESH_TOKEN = "chiripa_refresh_token";
  private static readonly KEY_WORKSPACE_ID = "chiripa_workspace_id";
  private static readonly KEY_INSTALLATION_ID = "chiripa_installation_id";
  private static readonly KEY_CAPABILITIES = "chiripa_capabilities";

  public static async getCredentials(): Promise<StoredCredentials> {
    if (typeof chrome === "undefined" || !chrome.storage?.local) {
      return {};
    }
    const res = await localGet([
      this.KEY_API_URL,
      this.KEY_ACCESS_TOKEN,
      this.KEY_REFRESH_TOKEN,
      this.KEY_WORKSPACE_ID,
      this.KEY_INSTALLATION_ID,
    ]);

    return {
      apiUrl: res[this.KEY_API_URL] as string | undefined,
      accessToken: res[this.KEY_ACCESS_TOKEN] as string | undefined,
      refreshToken: res[this.KEY_REFRESH_TOKEN] as string | undefined,
      workspaceId: res[this.KEY_WORKSPACE_ID] as string | null | undefined,
      installationId: res[this.KEY_INSTALLATION_ID] as string | undefined,
    };
  }

  public static async saveCredentials(creds: StoredCredentials): Promise<void> {
    if (typeof chrome === "undefined" || !chrome.storage?.local) return;
    const toSet: Record<string, string | null | undefined> = {};
    if (creds.apiUrl !== undefined) toSet[this.KEY_API_URL] = creds.apiUrl;
    if (creds.accessToken !== undefined) toSet[this.KEY_ACCESS_TOKEN] = creds.accessToken;
    if (creds.refreshToken !== undefined) toSet[this.KEY_REFRESH_TOKEN] = creds.refreshToken;
    if (creds.workspaceId !== undefined) toSet[this.KEY_WORKSPACE_ID] = creds.workspaceId;
    if (creds.installationId !== undefined) toSet[this.KEY_INSTALLATION_ID] = creds.installationId;

    await localSet(toSet);
  }

  public static async clearCredentials(): Promise<void> {
    if (typeof chrome === "undefined" || !chrome.storage?.local) return;
    await localRemove([
      this.KEY_ACCESS_TOKEN,
      this.KEY_REFRESH_TOKEN,
      this.KEY_WORKSPACE_ID,
    ]);
  }

  public static async getCapabilities(): Promise<Capabilities | null> {
    if (typeof chrome === "undefined" || !chrome.storage?.local) return null;
    const res = await localGet([this.KEY_CAPABILITIES]);
    return (res[this.KEY_CAPABILITIES] as Capabilities) || null;
  }

  public static async saveCapabilities(capabilities: Capabilities): Promise<void> {
    if (typeof chrome === "undefined" || !chrome.storage?.local) return;
    await localSet({ [this.KEY_CAPABILITIES]: capabilities });
  }
}
