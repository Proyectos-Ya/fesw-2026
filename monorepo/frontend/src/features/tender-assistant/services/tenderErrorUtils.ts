export function formatTenderAssistantError(err: unknown, fallbackMessage: string): string {
  if (
    err &&
    typeof err === "object" &&
    "status" in err &&
    typeof (err as { status: unknown }).status === "number"
  ) {
    const apiErr = err as { status: number; message?: string };
    const { status, message } = apiErr;

    if (status === 503) {
      return "No se pudo conectar al proveedor de IA. Inténtalo nuevamente en unos minutos.";
    }
    if (status === 502) {
      return "El asistente no pudo procesar la respuesta del modelo de IA. Intenta reformular tu pregunta.";
    }
    if (status === 400) {
      if (message && message !== "Bad Request") {
        return message;
      }
      return "Consulta inválida. Por favor revisa tu pregunta.";
    }
    if (status === 404) {
      return message && message !== "Not Found" ? message : "No se encontró la información solicitada.";
    }
    if (status >= 500) {
      if (
        message &&
        message !== "Internal Server Error" &&
        !message.toLowerCase().includes("traceback") &&
        !message.toLowerCase().includes("error:")
      ) {
        return message;
      }
      return "Ocurrió un problema en el servidor del asistente. Por favor reintenta en unos instantes.";
    }
  }

  if (err instanceof Error) {
    if (err.message === "Internal Server Error") {
      return "Ocurrió un problema en el servidor del asistente. Por favor reintenta en unos instantes.";
    }
    return err.message;
  }

  return fallbackMessage;
}
