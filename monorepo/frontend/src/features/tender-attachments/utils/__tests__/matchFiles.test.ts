import { describe, expect, it } from "vitest";

import { buildOfficialAttachment } from "../../test-utils";
import { matchDroppedFiles } from "../matchFiles";

function file(name: string): File {
  return new File(["x"], name);
}

const TECNICAS = buildOfficialAttachment({
  id: "a-1",
  name: "Especificaciones Técnicas.pdf",
  name_normalized: "especificaciones tecnicas.pdf",
  ext: "pdf",
});
const BASES = buildOfficialAttachment({
  id: "a-2",
  name: "Bases.pdf",
  name_normalized: "bases.pdf",
  ext: "pdf",
});

describe("matchDroppedFiles", () => {
  it("empareja ignorando tildes y mayúsculas", () => {
    const f = file("especificaciones tecnicas.PDF");

    const { matched, rejected } = matchDroppedFiles([f], [TECNICAS, BASES]);

    expect(matched).toEqual([{ file: f, attachment: TECNICAS }]);
    expect(rejected).toEqual([]);
  });

  it.each([["Bases (1).pdf"], ["Bases(1).pdf"]])(
    "tolera el sufijo de descarga repetida: %s",
    (nombre) => {
      const f = file(nombre);

      const { matched } = matchDroppedFiles([f], [TECNICAS, BASES]);

      expect(matched).toEqual([{ file: f, attachment: BASES }]);
    },
  );

  it("un archivo sin pareja queda como no_match", () => {
    const { matched, rejected } = matchDroppedFiles([file("otro.pdf")], [TECNICAS, BASES]);

    expect(matched).toEqual([]);
    expect(rejected).toEqual([{ fileName: "otro.pdf", reason: "no_match" }]);
  });

  it("dos filas oficiales que normalizan igual dejan el archivo como ambiguous", () => {
    const a = buildOfficialAttachment({
      id: "x-1",
      name: "Anexo.pdf",
      name_normalized: "anexo.pdf",
      ext: "pdf",
    });
    const b = buildOfficialAttachment({
      id: "x-2",
      name: "Anexo (2).pdf",
      name_normalized: "anexo.pdf",
      ext: "pdf",
    });

    const { matched, rejected } = matchDroppedFiles([file("Anexo.pdf")], [a, b]);

    expect(matched).toEqual([]);
    expect(rejected).toEqual([{ fileName: "Anexo.pdf", reason: "ambiguous" }]);
  });

  it("dos archivos para la misma fila: el primero se empareja y el segundo es duplicate", () => {
    const primero = file("Bases.pdf");
    const segundo = file("bases (1).pdf");

    const { matched, rejected } = matchDroppedFiles([primero, segundo], [BASES]);

    expect(matched).toEqual([{ file: primero, attachment: BASES }]);
    expect(rejected).toEqual([{ fileName: "bases (1).pdf", reason: "duplicate" }]);
  });

  it("conserva el orden en que se soltaron los archivos", () => {
    const a = file("Bases.pdf");
    const b = file("Especificaciones Técnicas.pdf");

    const { matched } = matchDroppedFiles([a, b], [TECNICAS, BASES]);

    expect(matched.map((m) => m.file)).toEqual([a, b]);
    expect(matched.map((m) => m.attachment.id)).toEqual(["a-2", "a-1"]);
  });
});
