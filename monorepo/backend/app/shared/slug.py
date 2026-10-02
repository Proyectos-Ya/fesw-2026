import re
import unicodedata


def slugify(text: str) -> str:
    """`ISO 9001:2015` → `iso-9001-2015`. Sin tildes, minúsculas y guiones."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")
