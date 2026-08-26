"""Agrega las filas y las imprime como tablas Markdown.

El plan del spike es explícito: *"las cifras están en tablas, por librería y por
categoría de calidad — no en prosa"*. Este módulo produce exactamente eso, para
pegar en `1.2-ocr-alternativas.md` sin transcribir nada a mano (transcribir es
donde se cuelan los números equivocados).
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from .corpus import Documento, resumen_corpus
from .runner import Fila

# Orden en que se muestran las categorías: de mejor a peor calidad, que es como
# se lee la pregunta "¿desde dónde deja de funcionar?".
ORDEN_CATEGORIAS = ("digital", "escaneado-limpio", "escaneado-malo", "sin-etiqueta")


def _promedio(valores: list[float]) -> float | None:
    return mean(valores) if valores else None


def _fmt(valor: float | None, decimales: int = 3) -> str:
    return "—" if valor is None else f"{valor:.{decimales}f}"


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor * 100:.0f}%"


def _orden(categoria: str) -> tuple[int, str]:
    if categoria in ORDEN_CATEGORIAS:
        return ORDEN_CATEGORIAS.index(categoria), categoria
    return len(ORDEN_CATEGORIAS), categoria


@dataclass
class Agregado:
    """Promedios de un extractor sobre una categoría de calidad."""

    extractor: str
    categoria: str
    documentos: int
    con_referencia: int
    errores: int
    cer: float | None
    wer: float | None
    token_recall: float | None
    token_precision: float | None
    diacritic_recall: float | None
    digit_recall: float | None
    reading_order: float | None
    tasa_paginas_vacias: float | None
    segundos_por_pagina: float | None
    rut_correcto: float | None
    razon_social_ok: float | None
    fechas_recall: float | None


def _metrica(filas: list[Fila], clave: str) -> list[float]:
    return [
        float(fila.texto[clave])
        for fila in filas
        if fila.texto is not None and clave in fila.texto
    ]


def _booleana(filas: list[Fila], atributo: str) -> float | None:
    valores = [getattr(fila, atributo) for fila in filas]
    presentes = [bool(v) for v in valores if v is not None]
    return mean(presentes) if presentes else None


def agregar(filas: list[Fila]) -> list[Agregado]:
    """Promedia por (extractor, categoría), que es el corte que decide el spike."""
    grupos: dict[tuple[str, str], list[Fila]] = {}
    for fila in filas:
        grupos.setdefault((fila.extractor, fila.categoria), []).append(fila)

    agregados = []
    for (extractor, categoria), grupo in grupos.items():
        # Los documentos que reventaron no entran a los promedios de calidad —
        # promediar un CER de 1.0 por un error de instalación mezcla dos cosas
        # distintas— pero sí se cuentan aparte en `errores`.
        validos = [f for f in grupo if not f.error]
        agregados.append(
            Agregado(
                extractor=extractor,
                categoria=categoria,
                documentos=len(grupo),
                con_referencia=sum(1 for f in validos if f.texto is not None),
                errores=len(grupo) - len(validos),
                cer=_promedio(_metrica(validos, "cer")),
                wer=_promedio(_metrica(validos, "wer")),
                token_recall=_promedio(_metrica(validos, "token_recall")),
                token_precision=_promedio(_metrica(validos, "token_precision")),
                diacritic_recall=_promedio(_metrica(validos, "diacritic_recall")),
                digit_recall=_promedio(_metrica(validos, "digit_recall")),
                reading_order=_promedio(_metrica(validos, "reading_order")),
                tasa_paginas_vacias=_promedio(
                    [
                        f.paginas_vacias / f.paginas
                        for f in validos
                        if f.paginas
                    ]
                ),
                segundos_por_pagina=_promedio(
                    [f.segundos_por_pagina for f in validos if f.paginas]
                ),
                rut_correcto=_booleana(validos, "rut_correcto"),
                razon_social_ok=_booleana(validos, "razon_social_ok"),
                fechas_recall=_promedio(
                    [f.fechas_recall for f in validos if f.fechas_recall is not None]
                ),
            )
        )

    return sorted(agregados, key=lambda a: (_orden(a.categoria), a.extractor))


def _tabla(encabezados: list[str], filas: list[list[str]]) -> str:
    lineas = ["| " + " | ".join(encabezados) + " |"]
    lineas.append("|" + "|".join("---" for _ in encabezados) + "|")
    for fila in filas:
        lineas.append("| " + " | ".join(fila) + " |")
    return "\n".join(lineas)


def tabla_texto(agregados: list[Agregado]) -> str:
    """La tabla principal: calidad de extracción de texto, la que decide el RAG."""
    filas = [
        [
            a.categoria,
            a.extractor,
            str(a.con_referencia),
            _fmt(a.cer),
            _fmt(a.wer),
            _pct(a.token_recall),
            _pct(a.token_precision),
            _pct(a.diacritic_recall),
            _pct(a.digit_recall),
            _pct(a.reading_order),
            _pct(a.tasa_paginas_vacias),
            _fmt(a.segundos_por_pagina, 2),
        ]
        for a in agregados
    ]
    return _tabla(
        [
            "Calidad",
            "Extractor",
            "Docs",
            "CER ↓",
            "WER ↓",
            "Recall tok ↑",
            "Precis tok ↑",
            "Tildes ↑",
            "Dígitos ↑",
            "Orden ↑",
            "Pág. vacías ↓",
            "s/pág ↓",
        ],
        filas,
    )


def tabla_campos(agregados: list[Agregado]) -> str:
    """Métricas de campo: lo que necesitan el onboarding (#156) y la validación (#157)."""
    filas = [
        [
            a.categoria,
            a.extractor,
            _pct(a.rut_correcto),
            _pct(a.razon_social_ok),
            _pct(a.fechas_recall),
        ]
        for a in agregados
        if any(
            v is not None for v in (a.rut_correcto, a.razon_social_ok, a.fechas_recall)
        )
    ]
    if not filas:
        return (
            "_Ningún documento del corpus trae `.gt.json` con campos esperados, "
            "así que no hay métricas de campo._"
        )
    return _tabla(
        ["Calidad", "Extractor", "RUT exacto ↑", "Razón social ↑", "Fechas ↑"], filas
    )


def tabla_corpus(documentos: list[Documento]) -> str:
    resumen = resumen_corpus(documentos)
    filas = [
        [categoria, str(datos["documentos"]), str(datos["con_texto_esperado"])]
        for categoria, datos in sorted(resumen.items(), key=lambda kv: _orden(kv[0]))
    ]
    total = sum(d["documentos"] for d in resumen.values())
    filas.append(
        ["**total**", f"**{total}**", f"**{sum(d['con_texto_esperado'] for d in resumen.values())}**"]
    )
    return _tabla(["Calidad", "Documentos", "Con `.gt.txt`"], filas)


def tabla_disponibilidad(estado: dict[str, str]) -> str:
    filas = [
        [nombre, "✅ disponible" if not motivo else f"❌ {motivo}"]
        for nombre, motivo in estado.items()
    ]
    return _tabla(["Extractor", "Estado"], filas)


def advertencias(documentos: list[Documento], filas: list[Fila]) -> list[str]:
    """Avisos que evitan leer un número como si significara más de lo que significa."""
    avisos = []
    resumen = resumen_corpus(documentos)
    total = sum(d["documentos"] for d in resumen.values())

    if total < 20:
        avisos.append(
            f"El corpus tiene {total} documentos. El plan pide ~30 y advierte que "
            "bajo ~20 las tasas no son representativas: sirven para detectar un "
            "extractor roto, no para elegir entre dos que funcionan."
        )

    faltantes = [c for c in ORDEN_CATEGORIAS[:3] if c not in resumen]
    if faltantes:
        avisos.append(
            "Sin documentos en: "
            + ", ".join(f"`{c}`" for c in faltantes)
            + ". La pregunta del spike es desde qué calidad deja de funcionar, y "
            "sin esas categorías no se puede responder (ver `degradar.py`)."
        )

    sin_referencia = [d for d in documentos if not d.tiene_texto_esperado]
    if sin_referencia:
        avisos.append(
            f"{len(sin_referencia)} de {total} documentos no tienen `.gt.txt`, "
            "así que no aportan CER/WER ni recall: solo tiempo y páginas vacías."
        )

    con_error = [f for f in filas if f.error]
    if con_error:
        avisos.append(f"{len(con_error)} extracciones terminaron en error (ver detalle).")

    return avisos


def tabla_errores(filas: list[Fila]) -> str:
    con_error = [f for f in filas if f.error]
    if not con_error:
        return "_Sin errores._"
    return _tabla(
        ["Extractor", "Documento", "Error"],
        [[f.extractor, f.documento, f.error or ""] for f in con_error],
    )
