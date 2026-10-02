"""Filtro sintáctico de prompt injection en instrucciones libres del usuario.

Primera barrera, barata y sin IA: frases típicas de "ignora tus instrucciones".
No reemplaza la segunda, que son las directivas de seguridad de cada prompt y
tratar lo del usuario como datos de baja prioridad.

Lo usan el análisis profundo y la regeneración del borrador de postulación. El
asistente de licitaciones tiene sus propios patrones
(`AskTenderAssistantUseCase.FORBIDDEN_PROMPT_PATTERNS`).
"""

FRASES_DE_INYECCION: tuple[str, ...] = (
    "ignora las instrucciones",
    "ignora los requisitos",
    "ignore instructions",
    "ignore previous instructions",
    "system prompt",
    "override instructions",
    "anula las instrucciones",
    "ignorar las instrucciones",
    "cambia el porcentaje",
)


def frase_de_inyeccion(texto: str | None) -> str | None:
    """La primera frase de inyección que aparece en el texto, o None si no hay."""
    if not texto:
        return None
    limpio = texto.lower().strip()
    return next((frase for frase in FRASES_DE_INYECCION if frase in limpio), None)
