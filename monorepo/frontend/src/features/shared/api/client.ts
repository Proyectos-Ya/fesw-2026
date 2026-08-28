// El fallback a localhost solo vale en desarrollo. En un build de producción,
// caer a localhost en silencio hace que el frontend desplegado llame al equipo
// del propio visitante: no falla al construir, falla en la cara del usuario y
// sin ninguna pista. Por eso acá revienta el build en vez de arrancar mal.
function resolverApiUrl(): string {
  const declarada = process.env.NEXT_PUBLIC_API_URL;
  if (declarada) return declarada;
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "NEXT_PUBLIC_API_URL no está definida. Es obligatoria fuera de desarrollo: " +
        "sin ella el frontend apuntaría a http://localhost:8000, que en el " +
        "navegador del usuario no es el backend.",
    );
  }
  return "http://localhost:8000";
}

const API_URL = resolverApiUrl();
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
