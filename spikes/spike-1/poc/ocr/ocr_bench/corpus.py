"""Carga del corpus etiquetado: documentos, ground truth y categoría de calidad.

Convención de archivos (sin base de datos ni formato propietario, para que
cualquiera pueda agregar un documento copiándolo a una carpeta):

    corpus/
      digital/
        bases-123.pdf
        bases-123.gt.txt      ← texto correcto completo, para las métricas de RAG
        bases-123.gt.json     ← campos esperados, para las métricas de #156/#157
      escaneado-limpio/
        e-rut-empresa.pdf
      escaneado-malo/
        cert-vigencia-foto.pdf

La **categoría de calidad es el nombre de la carpeta**. Es lo que permite
responder la pregunta que el spike tiene que contestar —"¿desde qué calidad de
documento deja de funcionar?"— sin depender de que alguien mantenga una tabla
aparte sincronizada.

Ambos ground truth son opcionales y se miden por separado:

- sin `.gt.txt` el documento igual entra al benchmark, pero solo aporta métricas
  que no necesitan referencia (tiempo, páginas vacías, caracteres extraídos);
- sin `.gt.json` no se miden campos.

Formato de `.gt.json` (todos los campos son opcionales):

    {
      "tipo": "e-rut",
      "rut": "76.086.428-5",
      "razon_social": "MGM Auditores Consultores Ltda",
      "fechas": ["15/03/2026"],
      "nota": "foto de celular, con sombra en el margen derecho"
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Las tres categorías del plan del spike. Cualquier otra carpeta se acepta
# igual —el benchmark no debe romperse por un nombre nuevo— pero se marca, para
# que un typo en el nombre de carpeta no pase inadvertido como categoría nueva.
CATEGORIAS_CONOCIDAS = ("digital", "escaneado-limpio", "escaneado-malo")

SIN_ETIQUETA = "sin-etiqueta"

# `.doc` (el formato binario OLE2 de Word 97-2003, no `.docx`) se incluye a
# propósito aunque **ningún extractor del registro lo sepa leer todavía**. La
# alternativa —excluirlo de `EXTENSIONES`— lo haría desaparecer del corpus sin
# ningún rastro: ni como documento medido, ni como error, ni como omitido. Un
# corpus real de Compra Ágil sí trae `.doc` (formularios antiguos que nadie
# resubió en formato nuevo), y `runner.advertir_sin_cobertura` es lo que deja
# ese vacío visible en el informe en vez de restar silenciosamente del total.
EXTENSIONES = (".pdf", ".docx", ".doc")


@dataclass(frozen=True)
class Documento:
    """Un documento del corpus con lo que se sepa de él."""

    ruta: Path
    categoria: str
    tipo: str = "desconocido"
    texto_esperado: str | None = None
    rut: str | None = None
    razon_social: str | None = None
    fechas: list[str] = field(default_factory=list)
    nota: str = ""

    @property
    def nombre(self) -> str:
        return self.ruta.name

    @property
    def tiene_texto_esperado(self) -> bool:
        return bool(self.texto_esperado and self.texto_esperado.strip())


def _leer_campos(ruta_json: Path) -> dict[str, object]:
    try:
        contenido = json.loads(ruta_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{ruta_json} no es JSON válido: {exc}") from exc
    if not isinstance(contenido, dict):
        raise ValueError(f"{ruta_json} debe contener un objeto JSON")
    return contenido


def cargar_documento(ruta: Path, categoria: str) -> Documento:
    """Arma un `Documento` leyendo sus archivos de ground truth si existen."""
    gt_texto = ruta.with_suffix(".gt.txt")
    gt_campos = ruta.with_suffix(".gt.json")

    texto = gt_texto.read_text(encoding="utf-8") if gt_texto.exists() else None
    campos = _leer_campos(gt_campos) if gt_campos.exists() else {}

    fechas = campos.get("fechas", [])
    if not isinstance(fechas, list):
        raise ValueError(f"{gt_campos}: 'fechas' debe ser una lista")

    return Documento(
        ruta=ruta,
        categoria=categoria,
        tipo=str(campos.get("tipo", "desconocido")),
        texto_esperado=texto,
        rut=str(campos["rut"]) if campos.get("rut") else None,
        razon_social=(
            str(campos["razon_social"]) if campos.get("razon_social") else None
        ),
        fechas=[str(f) for f in fechas],
        nota=str(campos.get("nota", "")),
    )


def cargar_corpus(raiz: Path) -> list[Documento]:
    """Recorre el corpus y devuelve los documentos ordenados por categoría.

    Los `.gt.txt`/`.gt.json` no se confunden con documentos porque el filtro es
    por extensión (`.pdf`, `.docx`). Un documento suelto en la raíz, sin carpeta
    de categoría, se admite como `sin-etiqueta`: es preferible que aparezca en
    el informe marcado a que desaparezca en silencio.
    """
    if not raiz.exists():
        raise FileNotFoundError(f"No existe el corpus en {raiz}")

    documentos: list[Documento] = []
    for ruta in sorted(raiz.rglob("*")):
        if not ruta.is_file() or ruta.suffix.lower() not in EXTENSIONES:
            continue
        relativa = ruta.relative_to(raiz)
        categoria = relativa.parts[0] if len(relativa.parts) > 1 else SIN_ETIQUETA
        documentos.append(cargar_documento(ruta, categoria))

    return sorted(documentos, key=lambda d: (d.categoria, d.nombre))


def resumen_corpus(documentos: list[Documento]) -> dict[str, dict[str, int]]:
    """Cuenta documentos por categoría y cuántos traen ground truth de texto.

    Sirve para el chequeo de representatividad del plan: menos de ~20 documentos
    en total, o una categoría con cero, y las tasas no significan nada.
    """
    resumen: dict[str, dict[str, int]] = {}
    for documento in documentos:
        fila = resumen.setdefault(
            documento.categoria, {"documentos": 0, "con_texto_esperado": 0}
        )
        fila["documentos"] += 1
        if documento.tiene_texto_esperado:
            fila["con_texto_esperado"] += 1
    return resumen
