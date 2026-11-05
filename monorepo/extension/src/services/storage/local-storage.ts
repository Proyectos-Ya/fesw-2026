/*
 * chrome.storage.local en ambos navegadores. En Firefox (MV2) el espacio `chrome.*`
 * funciona con callbacks y no devuelve promesas, así que `await chrome.storage.local.get()`
 * daba undefined. Se pasa el callback y, si la API además devuelve una promesa
 * (Chrome MV3, mocks de prueba), se usa la primera que responda.
 */
function settle<T>(invoke: (callback: (value: T) => void) => unknown): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    let done = false;
    const finish = (value: T) => {
      if (!done) {
        done = true;
        resolve(value);
      }
    };
    try {
      const result = invoke(finish);
      if (result && typeof (result as Promise<T>).then === "function") {
        (result as Promise<T>).then(finish, reject);
      }
    } catch (error) {
      reject(error);
    }
  });
}

/** Forma común de chrome.storage.local en ambos navegadores (callback opcional). */
interface StorageArea {
  get(keys: string[], callback: (items: Record<string, unknown> | undefined) => void): unknown;
  set(items: Record<string, unknown>, callback: () => void): unknown;
  remove(keys: string[], callback: () => void): unknown;
}

const area = () => chrome.storage.local as unknown as StorageArea;

export const localGet = (keys: string[]) =>
  settle<Record<string, unknown> | undefined>((cb) => area().get(keys, cb)).then((items) => items ?? {});

export const localSet = (items: Record<string, unknown>) => settle<void>((cb) => area().set(items, cb));

export const localRemove = (keys: string[]) => settle<void>((cb) => area().remove(keys, cb));
