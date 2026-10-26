/** WebCrypto no está disponible: la página no se abrió por https ni por localhost. */
export class InsecureContextError extends Error {
  constructor() {
    super(
      "Tu navegador no permite calcular la huella del archivo: abre Chiripa por https o localhost.",
    );
    this.name = "InsecureContextError";
  }
}

/**
 * Huella SHA-256 del archivo, en hex y minúsculas (64 caracteres).
 *
 * Lee el archivo entero en memoria (máximo 50 MB), por eso los archivos se
 * procesan en serie. WebCrypto solo existe en contextos seguros (https o
 * localhost): desde una IP de la red en desarrollo no está disponible.
 */
export async function sha256Hex(blob: Blob): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new InsecureContextError();
  const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}
