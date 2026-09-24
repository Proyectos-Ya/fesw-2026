import { describe, expect, it } from "vitest";
import { formatTenderAssistantError } from "../tenderErrorUtils";

describe("formatTenderAssistantError", () => {
  it("traduce error 503 a mensaje amigable de conexión de IA", () => {
    const errorObj = { status: 503, message: "Service Unavailable" };
    expect(formatTenderAssistantError(errorObj, "Fallback")).toBe(
      "No se pudo conectar al proveedor de IA. Inténtalo nuevamente en unos minutos."
    );
  });

  it("traduce error 502 a mensaje amigable de respuesta de IA no procesable", () => {
    const errorObj = { status: 502, message: "Bad Gateway" };
    expect(formatTenderAssistantError(errorObj, "Fallback")).toBe(
      "El asistente no pudo procesar la respuesta del modelo de IA. Intenta reformular tu pregunta."
    );
  });

  it("traduce error 400 con mensaje específico o genérico", () => {
    const errorWithDetail = { status: 400, message: "La consulta no puede estar vacía." };
    expect(formatTenderAssistantError(errorWithDetail, "Fallback")).toBe(
      "La consulta no puede estar vacía."
    );

    const generic400 = { status: 400, message: "Bad Request" };
    expect(formatTenderAssistantError(generic400, "Fallback")).toBe(
      "Consulta inválida. Por favor revisa tu pregunta."
    );
  });

  it("sanitiza errores 500 y 'Internal Server Error' sin exponerlos crudos", () => {
    const error500 = { status: 500, message: "Internal Server Error" };
    expect(formatTenderAssistantError(error500, "Fallback")).toBe(
      "Ocurrió un problema en el servidor del asistente. Por favor reintenta en unos instantes."
    );

    const rawError = new Error("Internal Server Error");
    expect(formatTenderAssistantError(rawError, "Fallback")).toBe(
      "Ocurrió un problema en el servidor del asistente. Por favor reintenta en unos instantes."
    );
  });

  it("mantiene mensajes de error legibles en español lanzados por la aplicación", () => {
    const customError = new Error("El archivo 'corrupto.pdf' no posee una cabecera PDF válida o está dañado.");
    expect(formatTenderAssistantError(customError, "Fallback")).toBe(
      "El archivo 'corrupto.pdf' no posee una cabecera PDF válida o está dañado."
    );
  });

  it("retorna fallbackMessage ante tipos desconocidos", () => {
    expect(formatTenderAssistantError(null, "Mensaje por defecto")).toBe("Mensaje por defecto");
    expect(formatTenderAssistantError("cadena suelta", "Mensaje por defecto")).toBe("Mensaje por defecto");
  });
});
