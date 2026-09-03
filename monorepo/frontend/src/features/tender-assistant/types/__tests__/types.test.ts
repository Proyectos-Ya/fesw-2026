import { describe, it, expect } from "vitest";
import {
  TenderChatMessage,
  DocumentDiscrepancy,
  Citation,
  MAX_ATTACHED_DOCUMENTS,
} from "../index";

describe("Tender Assistant Types and Contracts (HU-05.2)", () => {
  it("should define MAX_ATTACHED_DOCUMENTS constant as 10", () => {
    expect(MAX_ATTACHED_DOCUMENTS).toBe(10);
  });

  it("should construct a valid DocumentDiscrepancy object with conflicting sources", () => {
    const citationA: Citation = {
      document_name: "Bases_Administrativas.pdf",
      page_or_sheet: "Página 5",
      quote: "Plazo de 30 días corridos",
    };

    const citationB: Citation = {
      document_name: "Especificaciones_Tecnicas.pdf",
      page_or_sheet: "Página 12",
      quote: "Plazo de 45 días corridos",
    };

    const discrepancy: DocumentDiscrepancy = {
      topic: "Plazo de entrega y ejecución",
      description:
        "Las bases administrativas indican 30 días y las técnicas 45 días.",
      conflicting_sources: [citationA, citationB],
    };

    expect(discrepancy.topic).toBe("Plazo de entrega y ejecución");
    expect(discrepancy.description).toContain("30 días");
    expect(discrepancy.conflicting_sources).toHaveLength(2);
    expect(discrepancy.conflicting_sources[0].document_name).toBe(
      "Bases_Administrativas.pdf"
    );
  });

  it("should support enriched TenderChatMessage with discrepancies, warnings, unbacked_aspects and has_sufficient_info", () => {
    const message: TenderChatMessage = {
      id: "msg-123",
      session_id: "sess-456",
      tender_id: "tender-789",
      user_id: "user-001",
      role: "assistant",
      content: "Respuesta consolidada con discrepancias.",
      citations: [
        {
          document_name: "Bases.pdf",
          page_or_sheet: "Pág 1",
          quote: "Requisito general",
        },
      ],
      discrepancies: [
        {
          topic: "Plazo de entrega",
          description: "Contradicción entre bases y anexo",
          conflicting_sources: [],
        },
      ],
      warnings: [
        "El documento 'anexo_danado.pdf' está dañado y no pudo ser procesado.",
      ],
      unbacked_aspects: ["Presupuesto referencial disponible"],
      has_sufficient_info: false,
      created_at: "2026-09-02T20:00:00Z",
    };

    expect(message.discrepancies).toHaveLength(1);
    expect(message.warnings).toHaveLength(1);
    expect(message.warnings?.[0]).toContain("anexo_danado.pdf");
    expect(message.unbacked_aspects).toEqual(["Presupuesto referencial disponible"]);
    expect(message.has_sufficient_info).toBe(false);
  });
});
