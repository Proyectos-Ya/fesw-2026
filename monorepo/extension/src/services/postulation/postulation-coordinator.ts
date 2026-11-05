import { PostulationPackagePayload } from "../../types/schemas";
import { PostulationStore, postulationStore } from "./postulation-store";

export interface CoordinatorDependencies {
  store?: PostulationStore;
  tabsCreate?: (createProperties: chrome.tabs.CreateProperties) => Promise<chrome.tabs.Tab>;
  tabsUpdate?: (tabId: number, updateProperties: chrome.tabs.UpdateProperties) => Promise<chrome.tabs.Tab | undefined>;
  tabsSendMessage?: (tabId: number, message: unknown) => Promise<unknown>;
}

export class PostulationCoordinator {
  private store: PostulationStore;
  private tabsCreate: (createProperties: chrome.tabs.CreateProperties) => Promise<chrome.tabs.Tab>;
  private tabsUpdate: (tabId: number, updateProperties: chrome.tabs.UpdateProperties) => Promise<chrome.tabs.Tab | undefined>;
  private tabsSendMessage: (tabId: number, message: unknown) => Promise<unknown>;

  // Memoria en service worker para asociar licitación con la pestaña abierta
  private tenderTabMap: Map<string, number> = new Map();

  constructor(deps?: CoordinatorDependencies) {
    this.store = deps?.store ?? postulationStore;
    this.tabsCreate =
      deps?.tabsCreate ??
      ((props) =>
        new Promise((resolve, reject) => {
          chrome.tabs.create(props, (tab) => {
            if (chrome.runtime.lastError) {
              reject(chrome.runtime.lastError);
            } else {
              resolve(tab);
            }
          });
        }));

    this.tabsUpdate =
      deps?.tabsUpdate ??
      ((tabId, props) =>
        new Promise((resolve, reject) => {
          chrome.tabs.update(tabId, props, (tab) => {
            if (chrome.runtime.lastError) {
              reject(chrome.runtime.lastError);
            } else {
              resolve(tab);
            }
          });
        }));

    this.tabsSendMessage =
      deps?.tabsSendMessage ??
      ((tabId, msg) =>
        new Promise((resolve, reject) => {
          chrome.tabs.sendMessage(tabId, msg, (resp) => {
            if (chrome.runtime.lastError) {
              reject(chrome.runtime.lastError);
            } else {
              resolve(resp);
            }
          });
        }));
  }

  public async openPostulationTab(
    tenderCode: string,
    mpUrl?: string
  ): Promise<{ ok: boolean; tab_id?: number; error?: string }> {
    try {
      const url =
        mpUrl ||
        "https://www.mercadopublico.cl/Portal/Modules/Menu/Menu.aspx";

      const tab = await this.tabsCreate({
        url,
        active: false, // Regla CA3: abrir en pestaña nueva sin desenfocar Chiripa
      });

      if (tab?.id) {
        this.tenderTabMap.set(tenderCode, tab.id);
      }

      return { ok: true, tab_id: tab?.id };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, error: message };
    }
  }

  public async confirmPostulation(
    payload: PostulationPackagePayload
  ): Promise<{ ok: boolean; error?: string }> {
    try {
      await this.store.savePackage(payload);

      const tabId = this.tenderTabMap.get(payload.tender_code);
      if (typeof tabId === "number") {
        try {
          await this.tabsUpdate(tabId, { active: true });
        } catch {
          // Si la pestaña fue cerrada por el usuario, continuar sin error
        }

        try {
          await this.tabsSendMessage(tabId, {
            action: "PACKAGE_READY",
            tender_code: payload.tender_code,
          });
        } catch {
          // El content script puede no estar hidratado todavía
        }
      }

      return { ok: true };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, error: message };
    }
  }

  public async getPendingPackage(
    tenderCode: string
  ): Promise<PostulationPackagePayload | null> {
    return this.store.getPackage(tenderCode);
  }

  public async focusPostulationTab(
    tenderCode: string
  ): Promise<{ ok: boolean; error?: string }> {
    const tabId = this.tenderTabMap.get(tenderCode);
    if (typeof tabId === "number") {
      try {
        await this.tabsUpdate(tabId, { active: true });
        return { ok: true };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return { ok: false, error: message };
      }
    }
    return { ok: false, error: "Tab not found" };
  }
}

export const postulationCoordinator = new PostulationCoordinator();
