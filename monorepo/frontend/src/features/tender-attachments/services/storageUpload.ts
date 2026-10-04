/**
 * PUT directo al almacenamiento (R2, o el disco local en desarrollo).
 *
 * No usa `apiFetch` a propósito: ese agrega `Authorization` (R2 rechaza dos
 * mecanismos de auth y además le filtraría el token de Supabase a un tercero),
 * fija `Content-Type` JSON y pasa por `/api`, cuyo rewrite corta los cuerpos a
 * 10 MB. XHR y no fetch: es lo único que expone el progreso de subida.
 */
export class StorageUploadError extends Error {
  constructor(public readonly status: number) {
    super(
      status === 0
        ? "No se pudo conectar con el almacenamiento de archivos. Revisa tu conexión y reintenta."
        : `El almacenamiento rechazó el archivo (HTTP ${status}). Reintenta.`,
    );
    this.name = "StorageUploadError";
  }
}

interface PutToStorageOptions {
  url: string;
  method: "PUT";
  /** Exactamente las que devolvió el backend. `Content-Length` lo pone el navegador. */
  headers: Record<string, string>;
  body: Blob;
  /** Fracción entre 0 y 1. */
  onProgress?: (fraction: number) => void;
}

export function putToStorage(options: PutToStorageOptions): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(options.method, options.url);
    // Sin cookies: el almacenamiento es de otro origen y no necesita la sesión.
    xhr.withCredentials = false;
    for (const [name, value] of Object.entries(options.headers)) {
      xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (event: ProgressEvent) => {
      if (event.lengthComputable && event.total > 0) {
        options.onProgress?.(event.loaded / event.total);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new StorageUploadError(xhr.status));
    };
    xhr.onerror = () => reject(new StorageUploadError(0));
    xhr.onabort = () => reject(new StorageUploadError(0));
    xhr.send(options.body);
  });
}
