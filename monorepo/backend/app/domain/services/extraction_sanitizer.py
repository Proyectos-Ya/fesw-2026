"""Saneamiento y recorte defensivo de la salida de Gemini (plan 233, decisión 4)."""

import html
import re

REEMPLAZO_DE_ENLACE = "[enlace omitido]"
_URL = re.compile(
    r"(?i)\b(?:(?:https?|ftp)://|www\.)\S+"
    r"|\b(?:javascript|data|vbscript|file):\S*"
    # Dominio suelto con TLD común. El lookbehind deja pasar los correos (adquisiciones@x.cl).
    r"|(?<![@\w.-])(?:[a-z0-9-]+\.)+(?:cl|com|net|org|io|info|app|xyz|ly|me)\b(?:/\S*)?"
)
_ETIQUETA = re.compile(r"<[^<>]{0,500}>")
_CONTROL = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]"
)
LARGOS = {
    "cita": 600,
    "descripcion": 600,
    "texto": 2000,
    "monto_texto": 200,
    "lugar": 300,
    "plazo": 200,
    "unidad": 60,
    "tema": 120,
    "documento": 255,
    "pagina_u_hoja": 60,
}
MAXIMOS = {
    "requisitos": 40,
    "items": 100,
    "entregables": 30,
    "puntos_a_tener_en_cuenta": 15,
    "otras_citas": 10,
    "citas": 5,
}
_SIN_TOCAR = frozenset({"fecha", "hora", "tipo"})


def sanear_texto(valor: str, *, max_len: int | None = None) -> str:
    """Neutraliza etiquetas HTML, caracteres de control y URLs, recortando si excede el largo."""
    texto = _ETIQUETA.sub("", html.unescape(valor))
    texto = texto.replace("<", "‹").replace(">", "›")  # restos sueltos: nada que parezca HTML
    texto = _CONTROL.sub("", _URL.sub(REEMPLAZO_DE_ENLACE, texto))
    texto = " ".join(texto.split())
    if max_len is not None and len(texto) > max_len:
        texto = texto[: max_len - 1].rstrip() + "…"
    return texto


def sanear_extraccion(crudo: object, clave: str | None = None) -> object:
    """Recorre el JSON del modelo: quita `verificada`, recorta listas y textos, y neutraliza enlaces y HTML."""
    if isinstance(crudo, dict):
        return {
            k: sanear_extraccion(v, k)
            for k, v in crudo.items()
            if k != "verificada"
        }
    if isinstance(crudo, list):
        maximo = MAXIMOS.get(clave, len(crudo))
        return [sanear_extraccion(x, clave) for x in crudo[:maximo]]
    if isinstance(crudo, str):
        if clave in _SIN_TOCAR:
            return crudo
        return sanear_texto(crudo, max_len=LARGOS.get(clave))
    return crudo
