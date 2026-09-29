"""Diagnostica (y arregla) el choque de cabezas múltiples de Alembic.

    python -m scripts.migraciones                    # diagnostica; sale 1 si hay conflicto
    python -m scripts.migraciones --arreglar         # repunta el down_revision
    python -m scripts.migraciones --base origin/main

Automatiza el Problema A de `docs/guides/alembic-migraciones.md`. La diferencia
con `alembic heads` es que este script no se limita a contar: mira qué
migraciones son nuevas en tu rama para decidir cuál de las dos soluciones de la
guía corresponde, y nombra el archivo concreto que hay que tocar.

No abre conexión a la base de datos ni ejecuta `env.py`: solo lee el grafo de
`alembic/versions/` y consulta a git. Por eso sirve igual en el CI y en local
antes de abrir el PR, sin variables de entorno.
"""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from alembic.config import Config
from alembic.script import ScriptDirectory

RAIZ = Path(__file__).resolve().parent.parent

# `down_revision: str | Sequence[str] | None = "abc123"`, con comillas de
# cualquiera de los dos tipos: el autogenerate ha emitido ambas.
_DOWN_REVISION = re.compile(
    r"^(?P<prefijo>down_revision\s*(?::[^=]+)?=\s*)['\"][^'\"]+['\"]",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Revision:
    """Un archivo de `alembic/versions/` reducido a lo que importa acá."""

    revision: str
    # `None` en la primera migración; una tupla en las de merge.
    abajo: str | tuple[str, ...] | None
    archivo: str


Estado = Literal["ok", "repuntar", "merge", "manual"]


@dataclass(frozen=True)
class Diagnostico:
    estado: Estado
    cabezas: tuple[str, ...]
    # Solo en "repuntar": qué archivo tocar y a qué revisión apuntarlo.
    archivo: str | None = None
    destino: str | None = None


def _padres(revision: Revision) -> tuple[str, ...]:
    if revision.abajo is None:
        return ()
    if isinstance(revision.abajo, str):
        return (revision.abajo,)
    return tuple(revision.abajo)


def diagnosticar(
    historia: Sequence[Revision], nuevas: set[str]
) -> Diagnostico:
    """Decide qué hacer. Función pura: no toca disco, git ni la base.

    `nuevas` son las revisiones que la rama agrega respecto de su base, que es
    el dato que distingue las dos soluciones de la guía.
    """
    por_revision = {r.revision: r for r in historia}
    con_hijos = {padre for r in historia for padre in _padres(r)}
    cabezas = tuple(
        r.revision for r in historia if r.revision not in con_hijos
    )

    if len(cabezas) <= 1:
        return Diagnostico(estado="ok", cabezas=cabezas)

    cabezas_nuevas = [c for c in cabezas if c in nuevas]

    # Ninguna cabeza nació en esta rama: las dos ya viven en develop/main y
    # alguien pudo haberlas aplicado. Repuntar rompería su historial.
    if not cabezas_nuevas:
        return Diagnostico(estado="merge", cabezas=cabezas)

    # Con más de dos cabezas, o con dos propias, repuntar una no deja el grafo
    # lineal. No vale la pena adivinar.
    if len(cabezas) > 2 or len(cabezas_nuevas) != 1:
        return Diagnostico(estado="manual", cabezas=cabezas)

    # La cadena de la rama puede tener varias migraciones encadenadas: hay que
    # repuntar la que cuelga del ancestro común, no la cabeza.
    raiz = por_revision[cabezas_nuevas[0]]
    while True:
        padres = _padres(raiz)
        if len(padres) != 1 or padres[0] not in nuevas:
            break
        raiz = por_revision[padres[0]]

    # Una revisión con dos padres es un `merge heads` ya hecho: reescribir su
    # down_revision desharía la unión en silencio.
    if len(_padres(raiz)) > 1:
        return Diagnostico(estado="manual", cabezas=cabezas)

    destino = next(c for c in cabezas if c != cabezas_nuevas[0])
    return Diagnostico(
        estado="repuntar",
        cabezas=cabezas,
        archivo=raiz.archivo,
        destino=destino,
    )


def aplicar_arreglo(ruta: Path, destino: str) -> None:
    """Reescribe la línea `down_revision` del archivo, y nada más."""
    contenido = ruta.read_text()
    nuevo, sustituciones = _DOWN_REVISION.subn(
        lambda m: f'{m.group("prefijo")}"{destino}"', contenido, count=1
    )
    if sustituciones != 1:
        raise ValueError(
            f"No se encontró una línea `down_revision` con una revisión literal "
            f"en {ruta.name}. Si es una migración de merge (tupla) o la primera "
            f"del historial (None), hay que resolverlo a mano."
        )
    ruta.write_text(nuevo)


def _leer_historia() -> list[Revision]:
    script = ScriptDirectory.from_config(Config(str(RAIZ / "alembic.ini")))
    return [
        Revision(
            revision=s.revision,
            abajo=s.down_revision,
            archivo=Path(s.path).name,
        )
        for s in script.walk_revisions()
    ]


def _git(*argumentos: str) -> str | None:
    """Corre git y devuelve su salida, o None si no se pudo."""
    try:
        return subprocess.run(
            ["git", *argumentos],
            cwd=RAIZ, capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _revisiones_nuevas(base: str) -> set[str]:
    """Revisiones que esta rama agrega respecto de `base`, según git.

    Cuenta dos cosas, porque el script se usa en dos momentos distintos:
    las migraciones ya commiteadas en la rama (lo que ve el CI) y las que
    todavía están sin commitear (lo normal en local, justo después de correr
    `alembic revision --autogenerate`).

    Si git no puede responder —una base que no existe en el clon, un checkout
    superficial— devuelve solo las segundas, y el diagnóstico cae del lado
    conservador: pedirá `merge heads` en vez de proponer un repunte.
    """
    rutas: set[str] = set()

    commiteadas = _git(
        "diff", "--name-only", "--diff-filter=A",
        f"{base}...HEAD", "--", "alembic/versions/",
    )
    if commiteadas is None:
        print(
            f"Aviso: git no pudo comparar contra '{base}'. Solo se tendrán en "
            f"cuenta las migraciones sin commitear.",
            file=sys.stderr,
        )
    else:
        rutas.update(commiteadas.split())

    # `??` son archivos sin seguimiento y `A ` los ya agregados al índice.
    sin_commitear = _git(
        "status", "--porcelain", "--", "alembic/versions/"
    )
    for linea in (sin_commitear or "").splitlines():
        if linea[:2].strip() in {"??", "A"}:
            rutas.add(linea[3:].strip())

    # git imprime las rutas relativas a la raíz del repositorio, que en este
    # monorepo no es `monorepo/backend`.
    raiz_git = (_git("rev-parse", "--show-toplevel") or "").strip()
    base_rutas = Path(raiz_git) if raiz_git else RAIZ

    nuevas = set()
    for ruta in rutas:
        archivo = base_rutas / ruta
        if not archivo.exists():
            continue
        encontrada = re.search(
            r"^revision\s*(?::[^=]+)?=\s*['\"]([^'\"]+)['\"]",
            archivo.read_text(),
            re.MULTILINE,
        )
        if encontrada:
            nuevas.add(encontrada.group(1))
    return nuevas


def _informe(d: Diagnostico, base: str) -> str:
    """El mensaje, en Markdown: se lee igual en la terminal y en GitHub."""
    if d.estado == "ok":
        return f"OK: una sola cabeza de migraciones (`{d.cabezas[0]}`).\n"

    cabezas = "\n".join(f"- `{c}`" for c in d.cabezas)
    encabezado = (
        f"## Cabezas múltiples de Alembic\n\n"
        f"`alembic upgrade head` aborta sin aplicar nada, así que el despliegue "
        f"se caería. Cabezas actuales:\n\n{cabezas}\n\n"
    )

    if d.estado == "repuntar":
        return encabezado + (
            f"**Solución 1** de la guía (la migración sigue solo en tu rama): "
            f"repuntar su `down_revision` a `{d.destino}`.\n\n"
            f"Archivo: `alembic/versions/{d.archivo}`\n\n"
            f"```bash\n"
            f"python -m scripts.migraciones --base {base} --arreglar\n"
            f"```\n\n"
            f"> Esto vale si nadie aplicó todavía esa migración. Si la corriste "
            f"contra una base compartida, usa `alembic merge heads` en su "
            f"lugar: editar el `down_revision` de una migración ya aplicada "
            f"rompe ese historial.\n"
        )

    if d.estado == "merge":
        return encabezado + (
            "**Solución 2** de la guía: ninguna de las cabezas es nueva en esta "
            "rama, así que ya viven en `develop`/`main` y pueden estar "
            "aplicadas. No edites sus `down_revision`; une el grafo:\n\n"
            "```bash\n"
            'alembic merge heads -m "merge heads"\n'
            "```\n"
        )

    return encabezado + (
        "Hay más de dos cabezas, o varias nacieron en esta rama. El script no "
        "adivina el orden: revisa el Problema A de "
        "`docs/guides/alembic-migraciones.md` y resuélvelo a mano.\n"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--base",
        default="origin/develop",
        help="rama contra la que comparar (por defecto origin/develop)",
    )
    p.add_argument(
        "--arreglar",
        action="store_true",
        help="repunta el down_revision cuando es seguro hacerlo",
    )
    args = p.parse_args()

    diagnostico = diagnosticar(_leer_historia(), _revisiones_nuevas(args.base))
    informe = _informe(diagnostico, args.base)
    print(informe)

    # GitHub Actions publica esto en el resumen del job, con formato.
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a") as f:
            f.write(informe)

    if diagnostico.estado == "ok":
        return 0

    if args.arreglar and diagnostico.estado == "repuntar":
        assert diagnostico.archivo and diagnostico.destino
        aplicar_arreglo(
            RAIZ / "alembic" / "versions" / diagnostico.archivo,
            diagnostico.destino,
        )
        print(
            f"Arreglado: `{diagnostico.archivo}` ahora cuelga de "
            f"`{diagnostico.destino}`.\n"
            f"Revisa el cambio y commitéalo."
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
