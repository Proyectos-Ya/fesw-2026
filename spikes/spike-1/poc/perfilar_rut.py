"""Del RUT de una empresa a un borrador de perfil: rubro, región y palabras clave.

Contexto
--------
Prueba de punta a punta del mapeo de `1.1-onboarding.md`: se consulta
la empresa por RUT, se leen sus actividades económicas y de ahí se infieren los
rubros y las palabras clave del perfil, usando el diccionario de tres ejes de
`perfilamiento/diccionario.py`.

Salida: **nombre, región, rubros y palabras clave** — lo que el wizard debería
mostrar prellenado para que el usuario confirme o corrija.

Tres fuentes, la misma salida
-----------------------------
Web Empresario, ruts.info y SRE entregan la misma información en esquemas JSON
distintos (ver `perfilamiento/{web_empresario,ruts_info,sre}.py`). Cada una
tiene su propio adaptador; las tres convergen en el mismo `PerfilSugerido` vía
`perfilamiento/perfil.py`. Agregar una cuarta fuente es escribir un adaptador
más y una entrada en `FUENTES` — el resto de este script no cambia.

    python perfilar_rut.py --fuente web-empresario --rut 76.086.428-5
    python perfilar_rut.py --fuente ruts-info --rut 76.086.428-5
    python perfilar_rut.py --fuente sre --rut 76.668.304-5
    python perfilar_rut.py --fuente sre --payload respuesta.json   # sin red

Configuración de la API
-----------------------
Ninguna fuente tiene endpoint por defecto **a propósito**: consultar un servicio
externo tiene términos de uso y posiblemente costo, y no es algo que deba pasar
por omisión al correr un script. Cada fuente se configura con su propio par de
variables:

    export WEB_EMPRESARIO_URL='https://.../consulta?rut={rut}'
    export WEB_EMPRESARIO_TOKEN='...'          # opcional

    export RUTS_INFO_URL='https://.../consulta?rut={rut}'
    export RUTS_INFO_TOKEN='...'               # opcional

    export SRE_URL='https://sre.cl/api/company_info'
    export SRE_TOKEN='...'

`{rut}` se reemplaza por el RUT ya normalizado. Web Empresario y ruts.info son
GET: si el servicio espera el token como cabecera, se manda como
`Authorization: Bearer <token>`. **SRE es distinto: es POST**, con el RUT y el
token en un cuerpo JSON (`{"token": ..., "rut": ..., "version": "2.0"}`), no en
la URL ni en una cabecera — `perfilar_rut.py` lo detecta solo porque la entrada
de SRE en `FUENTES` declara `armar_cuerpo`.

Salida en JSON con `--json`, para encadenar con otra herramienta.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from perfilamiento.perfil import PerfilSugerido  # noqa: E402
from perfilamiento.ruts_info import desde_ruts_info  # noqa: E402
from perfilamiento.sre import desde_sre  # noqa: E402
from perfilamiento.vocabulario import a_region_del_front  # noqa: E402
from perfilamiento.web_empresario import desde_web_empresario  # noqa: E402
from puente_backend import asegurar_path  # noqa: E402

asegurar_path()

from app.domain.entities.supplier import is_valid_rut  # noqa: E402

TIEMPO_LIMITE = 20


@dataclass(frozen=True)
class Fuente:
    """Todo lo que este script necesita saber de una fuente para consultarla.

    Ninguna de las tres autentica igual — cada una necesitó su propio ajuste al
    integrarla, no una plantilla común:

    - **ruts.info**: GET, RUT en la URL (`{rut}`), token como
      `Authorization: Bearer <token>`.
    - **Web Empresario**: GET, RUT como segmento de la URL (`{rut}` igual, solo
      cambia dónde queda en la plantilla), token en la cabecera
      **`X-Api-Key`**, sin el prefijo `Bearer`.
    - **SRE**: POST, URL fija (sin `{rut}`), y tanto el RUT como el token van
      en un cuerpo JSON. `armar_cuerpo` arma ese cuerpo; su presencia es lo que
      decide que `consultar_api` tome el camino POST en vez de GET.
    """

    variable_url: str
    variable_token: str
    interpretar: Callable[[dict[str, Any]], PerfilSugerido]
    armar_cuerpo: Callable[[str, str | None], dict[str, Any]] | None = None
    # Solo para GET: nombre de la cabecera de autenticación y cómo se arma su
    # valor a partir del token. Por defecto, Bearer — el esquema más común.
    nombre_cabecera_token: str = "Authorization"
    formato_cabecera_token: str = "Bearer {token}"


def _cuerpo_sre(rut: str, token: str | None) -> dict[str, Any]:
    return {"token": token, "rut": rut, "version": "2.0"}


# Registro de fuentes. Agregar una nueva API es sumar una entrada acá — nada
# más en este archivo depende de cuál se eligió.
FUENTES: dict[str, Fuente] = {
    "web-empresario": Fuente(
        variable_url="WEB_EMPRESARIO_URL",
        variable_token="WEB_EMPRESARIO_TOKEN",
        interpretar=desde_web_empresario,
        # api-sii-chile.webempresario.com espera `X-Api-Key: <key>`, no Bearer.
        nombre_cabecera_token="X-Api-Key",
        formato_cabecera_token="{token}",
    ),
    "ruts-info": Fuente(
        variable_url="RUTS_INFO_URL",
        variable_token="RUTS_INFO_TOKEN",
        interpretar=desde_ruts_info,
    ),
    "sre": Fuente(
        variable_url="SRE_URL",
        variable_token="SRE_TOKEN",
        interpretar=desde_sre,
        armar_cuerpo=_cuerpo_sre,
    ),
}


def normalizar_rut(bruto: str) -> str:
    """Deja el RUT como `76086428-5`, que es lo que espera la mayoría de las APIs.

    Ojo: `BuscarProveedor` de Mercado Público exige lo contrario —con puntos—, y
    responde lo mismo para un formato equivocado que para una empresa que no
    existe (ver `1.1-onboarding.md`). Cada fuente tiene su formato y conviene no
    dar ninguno por supuesto.
    """
    limpio = bruto.replace(".", "").replace(" ", "").upper()
    if "-" not in limpio and len(limpio) > 1:
        limpio = f"{limpio[:-1]}-{limpio[-1]}"
    return limpio


def consultar_api(fuente: Fuente, nombre_fuente: str, rut: str) -> dict[str, Any]:
    """Consulta la API configurada para esta fuente. El único punto del PoC que sale a la red."""
    plantilla = os.environ.get(fuente.variable_url)
    if not plantilla:
        ejemplo_url = (
            "https://.../consulta"
            if fuente.armar_cuerpo
            else "https://.../consulta?rut={rut}"
        )
        raise SystemExit(
            f"Falta {fuente.variable_url}. Sin endpoint configurado este script "
            f"no sale a la red por su cuenta. Ejemplo:\n\n"
            f"    export {fuente.variable_url}='{ejemplo_url}'\n\n"
            f"O corre sobre una respuesta guardada: "
            f"--fuente {nombre_fuente} --payload respuesta.json"
        )

    token = os.environ.get(fuente.variable_token) if fuente.variable_token else None

    if fuente.armar_cuerpo:
        # POST con token en el cuerpo (SRE): la URL es fija, no lleva `{rut}`.
        cuerpo = json.dumps(fuente.armar_cuerpo(rut, token)).encode("utf-8")
        peticion = urllib.request.Request(
            plantilla,
            data=cuerpo,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    else:
        # GET con el RUT en la URL. La cabecera de autenticación depende de la
        # fuente (Bearer para ruts.info, X-Api-Key para Web Empresario).
        url = plantilla.format(rut=rut)
        peticion = urllib.request.Request(url, headers={"Accept": "application/json"})
        if token:
            peticion.add_header(
                fuente.nombre_cabecera_token,
                fuente.formato_cabecera_token.format(token=token),
            )

    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE) as respuesta:
            crudo = respuesta.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"la API respondió {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"no se pudo conectar: {exc.reason}") from exc

    # Se decodifica como UTF-8 con reemplazo: Web Empresario ya devuelve texto
    # mal codificado en algunos campos (ver `reparar_mojibake`), y reventar acá
    # perdería la respuesta completa por un acento.
    try:
        return json.loads(crudo.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"la respuesta no es JSON válido: {exc}") from exc


def a_salida(perfil: PerfilSugerido) -> dict[str, Any]:
    """Lo que pide el wizard, con las regiones en el vocabulario del front."""
    regiones_front = [
        nombre
        for region in perfil.regions
        if (nombre := a_region_del_front(region)) is not None
    ]
    return {
        "fuente": perfil.fuente,
        "nombre": perfil.legal_name,
        "rut": perfil.rut,
        "vigente": perfil.vigente,
        "regiones": regiones_front,
        "sectores": perfil.sectors,
        "palabras_clave": perfil.keywords,
        "dominio_comun": perfil.dominio,
        "avisos": perfil.avisos,
    }


def imprimir(perfil: PerfilSugerido) -> None:
    salida = a_salida(perfil)
    vigencia = {True: "vigente", False: "con término de giro", None: "sin determinar"}

    print(f"\n{salida['nombre']}  ({salida['rut']}, {vigencia[salida['vigente']]})  [{salida['fuente']}]")
    print(f"  Región : {', '.join(salida['regiones']) or '—'}")
    print(f"  Rubros : {', '.join(salida['sectores']) or '—'}")
    if salida["dominio_comun"]:
        print(f"  Dominio: {', '.join(salida['dominio_comun'])}")

    print("  Palabras clave:")
    for palabra in salida["palabras_clave"] or ["—"]:
        print(f"    - {palabra}")

    if perfil.sin_diccionario:
        print(
            "  Códigos sin entrada en el diccionario: "
            + ", ".join(str(c) for c in perfil.sin_diccionario)
        )
    if salida["avisos"]:
        print("  Avisos:")
        for aviso in salida["avisos"]:
            print(f"    · {aviso}")
    print()


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Infiere rubros y palabras clave de una empresa a partir de "
        "sus actividades económicas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fuente",
        choices=sorted(FUENTES),
        default="web-empresario",
        help="Qué API interpretar (por defecto: web-empresario).",
    )
    origen = parser.add_mutually_exclusive_group(required=True)
    origen.add_argument("--rut", help="RUT a consultar en la API de la fuente elegida.")
    origen.add_argument(
        "--payload",
        type=Path,
        help="Respuesta ya guardada, en JSON. No sale a la red.",
    )
    parser.add_argument("--json", action="store_true", help="Salida en JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    fuente = FUENTES[args.fuente]

    if args.payload:
        try:
            payload = json.loads(args.payload.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: no se pudo leer {args.payload}: {exc}", file=sys.stderr)
            return 1
    else:
        rut = normalizar_rut(args.rut)
        # Se valida antes de consultar: un RUT mal tipeado no merece una llamada
        # a un servicio externo, y el error es más claro acá.
        if not is_valid_rut(rut):
            print(f"error: {args.rut} no es un RUT válido", file=sys.stderr)
            return 1
        payload = consultar_api(fuente, args.fuente, rut)

    try:
        perfil = fuente.interpretar(payload)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(a_salida(perfil), ensure_ascii=False, indent=2))
    else:
        imprimir(perfil)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
