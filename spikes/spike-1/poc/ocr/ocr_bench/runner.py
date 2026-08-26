"""Ejecuta cada extractor sobre cada documento y arma las filas de resultado.

Separado de la CLI para poder probarlo sin tocar disco ni argumentos, y del
informe para poder agregar métricas sin tocar el formato de salida.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

from .corpus import Documento
from .dominio import RUT_DISPONIBLE, is_valid_rut
from .extractors import REGISTRO, Extractor
from .metrics import (
    MetricasTexto,
    coincide_razon_social,
    evaluar_fechas_esperadas,
    evaluar_texto,
    extraer_ruts,
)


@dataclass
class Fila:
    """Un documento medido con un extractor."""

    extractor: str
    familia: str
    documento: str
    categoria: str
    tipo: str
    paginas: int
    paginas_vacias: int
    segundos: float
    segundos_por_pagina: float
    caracteres: int
    error: str | None = None
    # Métricas de texto: solo si el documento trae `.gt.txt`.
    texto: dict[str, float | int] | None = None
    # Métricas de campo: solo si trae `.gt.json` con ese campo.
    rut_detectado: bool | None = None
    rut_correcto: bool | None = None
    rut_valido_dv: bool | None = None
    razon_social_ok: bool | None = None
    fechas_recall: float | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class Resultado:
    """Todo lo que produjo una corrida."""

    filas: list[Fila] = field(default_factory=list)
    omitidos: list[str] = field(default_factory=list)


def _normalizar_rut(rut: str) -> str:
    return rut.replace(".", "").replace(" ", "").upper()


def _medir_campos(fila: Fila, documento: Documento, texto: str) -> None:
    """Completa las métricas de campo sobre la fila, si hay qué comparar."""
    if documento.rut:
        detectados = extraer_ruts(texto)
        esperado = _normalizar_rut(documento.rut)
        fila.rut_detectado = bool(detectados)
        fila.rut_correcto = esperado in detectados
        if RUT_DISPONIBLE:
            # Distinción clave: un OCR que confunde un dígito produce un RUT con
            # forma perfecta pero dígito verificador inválido. Ese caso se puede
            # rechazar en la interfaz; el peligroso es el que además valida.
            fila.rut_valido_dv = any(is_valid_rut(r) for r in detectados)

    if documento.razon_social:
        fila.razon_social_ok = coincide_razon_social(documento.razon_social, texto)

    if documento.fechas:
        fila.fechas_recall = evaluar_fechas_esperadas(documento.fechas, texto)


def evaluar_documento(extractor: Extractor, documento: Documento) -> Fila:
    """Corre un extractor sobre un documento y mide todo lo que se pueda."""
    extraccion = extractor.extraer(documento.ruta)
    paginas = len(extraccion.paginas)
    texto = extraccion.texto

    fila = Fila(
        extractor=extractor.nombre,
        familia=extractor.familia,
        documento=documento.nombre,
        categoria=documento.categoria,
        tipo=documento.tipo,
        paginas=paginas,
        paginas_vacias=extraccion.paginas_vacias,
        segundos=round(extraccion.segundos, 3),
        segundos_por_pagina=round(extraccion.segundos / paginas, 3) if paginas else 0.0,
        caracteres=len(texto),
        error=extraccion.error,
    )

    if extraccion.error:
        return fila

    if documento.tiene_texto_esperado:
        metricas: MetricasTexto = evaluar_texto(documento.texto_esperado or "", texto)
        fila.texto = metricas.as_dict()

    _medir_campos(fila, documento, texto)
    return fila


def _sin_cobertura(documentos: list[Documento]) -> list[str]:
    """Documentos cuya extensión no soporta ningún extractor del registro.

    Es distinto de "extractor no instalado": acá no hay ningún candidato,
    instalado o no. Sin este chequeo, un documento así desaparece del informe
    sin dejar rastro — no está en ninguna fila, no está en ningún error — que es
    exactamente el vacío silencioso que este arnés existe para evitar. El caso
    real que lo motivó: un `.doc` legacy (Word 97-2003, formato OLE2) entre
    formularios de Compra Ágil, que ningún extractor de la escalera sabe leer.
    """
    avisos = []
    for documento in documentos:
        if not any(e.soporta(documento.ruta) for e in REGISTRO.values()):
            avisos.append(
                f"{documento.nombre}: ningún extractor soporta "
                f"'{documento.ruta.suffix}' — no se midió, no es un error"
            )
    return avisos


def correr(
    documentos: Iterable[Documento],
    extractores: Iterable[str] | None = None,
) -> Resultado:
    """Corre la matriz completa extractor × documento.

    Un extractor que no está instalado no falla la corrida: se anota en
    `omitidos` con el motivo y se sigue. La tabla final tiene que distinguir
    "no se probó" de "se probó y le fue mal".
    """
    nombres = list(extractores) if extractores else list(REGISTRO)
    documentos = list(documentos)
    resultado = Resultado()
    resultado.omitidos.extend(_sin_cobertura(documentos))

    for nombre in nombres:
        extractor = REGISTRO.get(nombre)
        if extractor is None:
            resultado.omitidos.append(f"{nombre}: no existe en el registro")
            continue

        ok, motivo = extractor.disponible()
        if not ok:
            resultado.omitidos.append(f"{nombre}: {motivo}")
            continue

        aplicables = [d for d in documentos if extractor.soporta(d.ruta)]
        if not aplicables:
            resultado.omitidos.append(
                f"{nombre}: ningún documento del corpus tiene extensión "
                f"{'/'.join(extractor.extensiones)}"
            )
            continue

        for documento in aplicables:
            resultado.filas.append(evaluar_documento(extractor, documento))

    return resultado
