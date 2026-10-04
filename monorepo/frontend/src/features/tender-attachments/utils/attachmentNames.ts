/**
 * Port exacto de `app/domain/services/attachment_names.py` del backend.
 *
 * Sirve solo para **emparejar** un archivo soltado con la fila oficial que le
 * corresponde: el backend vuelve a validar el nombre y es quien manda. Si una
 * regla cambia allá, cambia acá, y las dos tablas de pruebas son idénticas.
 */

// Sufijo que agrega el navegador al descargar dos veces el mismo archivo:
// "Bases (1).pdf" en Chrome y Edge, "Bases(1).pdf" en Firefox. Solo dígitos:
// "anexos (1,1-A, 2).docx" es un nombre oficial real y se conserva.
const DOWNLOAD_SUFFIX = /(?:\s*\(\d{1,3}\))+$/;
const SPACES = /\s+/g;
// Al menos una letra: "Versión 1.2" no tiene extensión "2".
const EXTENSION = /^(?=[a-z0-9]*[a-z])[a-z0-9]{1,10}$/;
// Rango de marcas combinantes y no `\p{M}`: el target del TS es ES2017.
const COMBINING_MARKS = /[̀-ͯ]/g;

/** NFC, casefold, sin tildes y con los espacios colapsados. */
function basic(name: string): string {
  // `ß` es lo que importa del casefold de Python que `toLowerCase` no cubre.
  const folded = name.normalize("NFC").toLowerCase().replace(/ß/g, "ss");
  return folded
    .normalize("NFD")
    .replace(COMBINING_MARKS, "")
    .normalize("NFC")
    .replace(SPACES, " ")
    .trim();
}

/** Separa raíz y extensión; sin extensión reconocible devuelve [base, ""]. */
function split(base: string): [string, string] {
  const dot = base.lastIndexOf(".");
  if (dot === -1) return [base, ""];
  const root = base.slice(0, dot);
  const ext = base.slice(dot + 1).trim();
  if (root.trim() === "" || !EXTENSION.test(ext)) return [base, ""];
  return [root.trim(), ext];
}

/** Extensión en minúsculas y sin punto; vacía si no hay una reconocible. */
export function attachmentExtension(name: string): string {
  return split(basic(name))[1];
}

/** Forma canónica del nombre: sin mayúsculas, tildes ni sufijo de descarga repetida. */
export function normalizeAttachmentName(name: string): string {
  const [root, ext] = split(basic(name));
  const clean = root.replace(DOWNLOAD_SUFFIX, "").trim();
  return ext ? `${clean}.${ext}` : clean;
}
