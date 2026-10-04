import { describe, expect, it } from "vitest";

import { attachmentExtension, normalizeAttachmentName } from "../attachmentNames";

/**
 * La misma tabla que `tests/unit/domain/test_attachment_names.py` del backend.
 * El backend manda: si una fila cambia allá, cambia acá, o un archivo que el
 * navegador cree válido lo rechazará el servidor (o al revés).
 */
describe("normalizeAttachmentName", () => {
  it.each([
    ["Especificaciones Técnicas.pdf", "especificaciones tecnicas.pdf"],
    ["ESPECIFICACIONES TECNICAS.PDF", "especificaciones tecnicas.pdf"],
    ["  Anexo   1 \t.docx ", "anexo 1.docx"],
    ["Bases (1).pdf", "bases.pdf"],
    ["Bases(2).pdf", "bases.pdf"],
    ["Bases (1) (2).pdf", "bases.pdf"],
    ["anexos (1,1-A, 2).docx", "anexos (1,1-a, 2).docx"],
    ["Año 2026 Ñuñoa.xlsx", "ano 2026 nunoa.xlsx"],
    ["Bases", "bases"],
    ["Bases (1)", "bases"],
  ])("normaliza %j a %j", (entrada, esperado) => {
    expect(normalizeAttachmentName(entrada)).toBe(esperado);
  });

  it("NFC y NFD de la misma palabra dan lo mismo", () => {
    const nfc = "Técnicas.pdf".normalize("NFC");
    const nfd = "Técnicas.pdf".normalize("NFD");

    expect(nfc).not.toBe(nfd);
    expect(normalizeAttachmentName(nfc)).toBe(normalizeAttachmentName(nfd));
  });

  it("una descarga repetida del navegador iguala al nombre oficial", () => {
    expect(normalizeAttachmentName("anexo 3 composicion personalidad juridica (1).XLSX")).toBe(
      normalizeAttachmentName("Anexo 3 Composición personalidad juridica.xlsx"),
    );
  });
});

describe("attachmentExtension", () => {
  it.each([
    ["Bases.PDF", "pdf"],
    ["anexos (1,1-A, 2).docx", "docx"],
    ["archivo.tar.gz", "gz"],
    ["foto.JPEG", "jpeg"],
    ["Planilla.xlsx ", "xlsx"],
    ["Bases", ""],
    [".pdf", ""],
    ["Versión 1.2", ""],
    ["Informe v1.2 final", ""],
  ])("la extensión de %j es %j", (entrada, esperado) => {
    expect(attachmentExtension(entrada)).toBe(esperado);
  });
});
