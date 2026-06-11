const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
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
 */
export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: controller.signal,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
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

  return response.json() as Promise<T>;
}
