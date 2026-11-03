import { PostulationPackagePayload } from "../../types/schemas";

interface StoredPackageEntry {
  tender_code: string;
  packageData: PostulationPackagePayload;
  expires_at: number;
}

const DB_NAME = "chiripa_postulation";
const DB_VERSION = 1;
const STORE_NAME = "packages";
const DEFAULT_TTL_MS = 30 * 60 * 1000; // 30 minutos

export class PostulationStore {
  private dbPromise: Promise<IDBDatabase> | null = null;

  private async getDB(): Promise<IDBDatabase> {
    if (this.dbPromise) {
      return this.dbPromise;
    }

    this.dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "tender_code" });
        }
      };

      request.onsuccess = () => {
        resolve(request.result);
      };

      request.onerror = () => {
        reject(request.error);
      };
    });

    return this.dbPromise;
  }

  public async savePackage(
    packageData: PostulationPackagePayload,
    ttlMs: number = DEFAULT_TTL_MS
  ): Promise<void> {
    const db = await this.getDB();
    const expires_at = Date.now() + ttlMs;
    const entry: StoredPackageEntry = {
      tender_code: packageData.tender_code,
      packageData,
      expires_at,
    };

    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const req = store.put(entry);

      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });

    // Sincronizar metadatos en chrome.storage.local si está presente
    if (typeof chrome !== "undefined" && chrome.storage?.local) {
      const metaKey = `postulation_meta_${packageData.tender_code}`;
      await chrome.storage.local.set({
        [metaKey]: {
          tender_code: packageData.tender_code,
          company_rut: packageData.company_rut,
          total_clp: packageData.total_clp,
          items_count: packageData.items.length,
          files_count: packageData.files.length,
          expires_at,
        },
      });
    }
  }

  public async getPackage(
    tender_code: string
  ): Promise<PostulationPackagePayload | null> {
    const db = await this.getDB();

    const entry = await new Promise<StoredPackageEntry | undefined>(
      (resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readonly");
        const store = tx.objectStore(STORE_NAME);
        const req = store.get(tender_code);

        req.onsuccess = () => resolve(req.result as StoredPackageEntry | undefined);
        req.onerror = () => reject(req.error);
      }
    );

    if (!entry) {
      return null;
    }

    // Comprobar TTL
    if (Date.now() > entry.expires_at) {
      await this.clearPackage(tender_code);
      return null;
    }

    return entry.packageData;
  }

  public async clearPackage(tender_code: string): Promise<void> {
    const db = await this.getDB();

    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const req = store.delete(tender_code);

      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });

    if (typeof chrome !== "undefined" && chrome.storage?.local) {
      const metaKey = `postulation_meta_${tender_code}`;
      await chrome.storage.local.remove([metaKey]);
    }
  }
}

export const postulationStore = new PostulationStore();
