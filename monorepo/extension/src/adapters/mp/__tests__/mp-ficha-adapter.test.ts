import { describe, expect, it } from "vitest";
import { MpFichaAdapter } from "../mp-ficha-adapter";

describe("MpFichaAdapter", () => {
  it("extrae código de licitación desde search params", () => {
    const adapter = new MpFichaAdapter();
    const code = adapter.extractCode("?code=1234-5-COT26");
    expect(code).toBe("1234-5-COT26");
  });

  it("extrae código desde elemento en DOM si no está en URL", () => {
    const mockDoc = {
      querySelector: (selector: string) => {
        if (selector.includes("tender-code")) {
          return { textContent: "Licitación 5678-9-COT26 del Servicio" };
        }
        return null;
      },
    } as unknown as Document;

    const adapter = new MpFichaAdapter(mockDoc);
    const code = adapter.extractCode("");
    expect(code).toBe("5678-9-COT26");
  });

  it("detecta primer llamado cuando no hay texto de segundo llamado", () => {
    const mockDoc = {
      body: {
        innerText: "Fecha de cierre: 15-10-2026 18:00\nEstado: Publicada",
      },
    } as unknown as Document;

    const adapter = new MpFichaAdapter(mockDoc);
    const info = adapter.extractCallInfo();
    expect(info.call_number).toBe(1);
    expect(info.first_call).toBe("15-10-2026 18:00");
    expect(info.second_call).toBeNull();
  });

  it("detecta segundo llamado y extrae fechas de cierre", () => {
    const mockDoc = {
      body: {
        innerText:
          "Convocatoria a Segundo Llamado.\nCierre primer llamado: 10-10-2026 15:00\nCierre segundo llamado: 20-10-2026 18:00",
      },
    } as unknown as Document;

    const adapter = new MpFichaAdapter(mockDoc);
    const info = adapter.extractCallInfo();
    expect(info.call_number).toBe(2);
    expect(info.first_call).toBe("10-10-2026 15:00");
    expect(info.second_call).toBe("20-10-2026 18:00");
  });

  it("extrae tabla de anexos oficiales correctamente", () => {
    const mockRows = [
      {
        getAttribute: () => "doc-101",
        querySelector: (sel: string) => {
          if (sel.includes("nombre-archivo")) return { textContent: "Bases_Administrativas.pdf" };
          return null;
        },
      },
      {
        getAttribute: () => "doc-102",
        querySelector: (sel: string) => {
          if (sel.includes("nombre-archivo")) return { textContent: "Especificaciones_Tecnicas.docx" };
          return null;
        },
      },
    ];

    const mockDoc = {
      querySelectorAll: (sel: string) => {
        if (sel.includes("adjuntos")) return mockRows;
        return [];
      },
    } as unknown as Document;

    const adapter = new MpFichaAdapter(mockDoc);
    const attachments = adapter.extractAttachments();

    expect(attachments).toHaveLength(2);
    expect(attachments[0]).toEqual({
      mp_document_id: "doc-101",
      name: "Bases_Administrativas.pdf",
    });
    expect(attachments[1]).toEqual({
      mp_document_id: "doc-102",
      name: "Especificaciones_Tecnicas.docx",
    });
  });
});
