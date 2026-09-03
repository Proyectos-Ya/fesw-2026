/**
 * La API se consume por una ruta relativa del propio dominio, y `next.config.ts`
 * la reenvía al backend con un rewrite.
 *
 * Antes esto era la variable pública con el dominio del backend en Railway. Eso
 * convertía la cookie de sesión en una cookie de tercera parte: el navegador la
 * guardaba pero no la devolvía, y en producción el login entraba en bucle
 * —`POST /auth/login` 200 y `GET /auth/me` 401, una y otra vez—. Ya no hay
 * variable que declarar ni, por lo tanto, forma de volver a apuntar el navegador
 * a otro dominio por descuido: el destino real vive en `BACKEND_ORIGIN`, del
 * lado del servidor.
 */
const API_BASE_PATH = "/api";

const REQUEST_TIMEOUT_MS = 60_000; 
// Este numero es un balance entre no hacer esperar al usuario demasiado tiempo y no cancelar solicitudes legítimas en conexiones lentas.

/** Error de una respuesta HTTP no exitosa del backend. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Error lanzado cuando el servidor no responde dentro del tiempo límite. */
export class TimeoutError extends Error {
  constructor() {
    super("La solicitud tardó demasiado. Por favor, inténtalo nuevamente.");
    this.name = "TimeoutError";
  }
}

/**
 * Cliente fetch tipado contra la API de ProyectosYA.
 * Envía la cookie de sesión (credentials) y normaliza los errores de FastAPI,
 * que vienen como `{ detail: string }`.
 *
 * `path` es la ruta del backend tal cual (`/auth/me`); el prefijo `/api` lo
 * agrega esta función.
 */
export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_PATH}${path}`, {
      ...options,
      signal: controller.signal,
      credentials: "include",
      headers: {
        ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...options?.headers,
      },

    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new TimeoutError();
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body: unknown = await response.json();
      if (
        body &&
        typeof body === "object" &&
        "detail" in body &&
        typeof (body as { detail: unknown }).detail === "string"
      ) {
        detail = (body as { detail: string }).detail;
      }
    } catch {
      // Respuesta sin cuerpo JSON: se mantiene el statusText.
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content (ej: logout) no trae cuerpo: parsearlo como JSON lanzaría.
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
