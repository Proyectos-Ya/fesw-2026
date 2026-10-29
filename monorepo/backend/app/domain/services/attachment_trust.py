"""Qué versión de un anexo oficial se comparte entre empresas (plan 233, decisión 6).

Funciones puras: reciben todas las filas no purgadas de un anexo oficial (los
aportes de cada empresa y las versiones canónicas, sin empresa) y las personas de
cada empresa. El caso de uso solo aplica la decisión, con el anexo bloqueado.

- Una versión se comparte cuando la confirman dos fuentes independientes: dos
  empresas sin personas en común, o una captura de la extensión y otra fuente que
  no sea la misma persona.
- Una subida suelta no se comparte, no bloquea y no ve a las demás: si su estado
  dependiera de los privados ajenos, subir cualquier archivo serviría para
  averiguar si otra empresa trabaja esa licitación.
- Hay conflicto con dos o más versiones respaldadas (corroboradas, de la extensión
  o ya compartidas) y ninguna gana. Mientras dure, no se comparte nada.
- Lo ya compartido solo lo cuestiona la extensión, y la extensión arbitra.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations
from uuid import UUID

from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.services.attachment_files import tiene_archivo

# Empresa -> sus personas: el dueño legado y todas sus membresías, en cualquier estado.
Personas = Mapping[UUID, frozenset[UUID]]
_VIVAS = frozenset({AttachmentTrust.CORROBORATED, AttachmentTrust.CONFLICT})


@dataclass(frozen=True)
class EstadoCanonico:
    visibility: AttachmentVisibility
    trust: AttachmentTrust


@dataclass(frozen=True)
class DecisionDeConfianza:
    ganador: str | None  # sha256 de la versión que ven todas las empresas
    en_conflicto: bool
    aportes: dict[UUID, AttachmentTrust]  # confianza nueva de cada fila de empresa
    canonicos: dict[UUID, EstadoCanonico]  # estado nuevo de cada canónica existente
    crear_canonico: str | None  # sha que hay que copiar a shared/


def es_canonico(archivo: AttachmentFile) -> bool:
    return archivo.workspace_id is None


def es_propio(archivo: AttachmentFile, workspace_id: UUID | None) -> bool:
    """Nunca `archivo.workspace_id == workspace_id` a secas: `None == None`."""
    return workspace_id is not None and archivo.workspace_id == workspace_id


def visibilidad_efectiva(archivo: AttachmentFile) -> AttachmentVisibility:
    """Quién ve este contenido.

    El aporte propio ya corroborado lo ven todas las empresas (por su copia
    canónica), aunque su fila siga siendo privada: la etiqueta que se muestra y la
    regla de borrado salen de acá.
    """
    if archivo.visibility == AttachmentVisibility.SHARED:
        return AttachmentVisibility.SHARED
    if (
        not es_canonico(archivo)
        and archivo.trust == AttachmentTrust.CORROBORATED
        and tiene_archivo(archivo)
    ):
        return AttachmentVisibility.SHARED
    return AttachmentVisibility.PRIVATE


def _personas_de(archivo: AttachmentFile, personas: Personas) -> set[UUID]:
    propias: set[UUID] = set()
    if archivo.workspace_id is not None:
        propias |= personas.get(archivo.workspace_id, frozenset())
    if archivo.uploader_user_id is not None:
        propias.add(archivo.uploader_user_id)
    return propias


def son_independientes(a: AttachmentFile, b: AttachmentFile, personas: Personas) -> bool:
    """¿Se pueden confirmar mutuamente? Nadie se corrobora a sí mismo."""
    if a.id == b.id:
        return False
    # Ni la misma persona, ni siquiera desde dos empresas o por dos canales.
    if a.uploader_user_id is not None and a.uploader_user_id == b.uploader_user_id:
        return False
    # La captura de la extensión viene de Mercado Público, no de un archivo que
    # eligió una persona: es otro canal aunque las empresas compartan gente.
    if AttachmentFileSource.EXTENSION in (a.source, b.source):
        return True
    if a.workspace_id is None or b.workspace_id is None or a.workspace_id == b.workspace_id:
        return False
    return _personas_de(a, personas).isdisjoint(_personas_de(b, personas))


def _corroborada(grupo: list[AttachmentFile], personas: Personas) -> bool:
    return any(son_independientes(a, b, personas) for a, b in combinations(grupo, 2))


def _version_vigente(canonicos: list[AttachmentFile]) -> str | None:
    """La compartida o, si la extensión la suspendió, la suspendida."""
    vivas = [c for c in canonicos if c.trust in _VIVAS]
    if not vivas:
        return None
    compartida = next((c for c in vivas if c.visibility == AttachmentVisibility.SHARED), None)
    return (compartida or max(vivas, key=lambda c: c.created_at)).sha256


def _elegir_ganador(
    vigente: str | None, corroboradas: set[str], con_extension: set[str]
) -> str | None:
    if len(con_extension) > 1:
        return None  # la extensión se contradice
    if con_extension:
        (de_la_extension,) = con_extension
        if de_la_extension == vigente or de_la_extension in corroboradas:
            return de_la_extension  # la extensión arbitra
        return None
    if vigente is not None:
        return vigente  # dos empresas no descomparten
    return next(iter(corroboradas)) if len(corroboradas) == 1 else None


def decidir_confianza(
    archivos: Iterable[AttachmentFile], personas: Personas
) -> DecisionDeConfianza:
    """Recalcula por completo el estado de un anexo: sin transiciones incrementales.

    Es idempotente (aplicar el resultado y volver a decidir no cambia nada), así
    que no hay estados intermedios bajo concurrencia.
    """
    filas = list(archivos)
    canonicos = [a for a in filas if es_canonico(a)]
    aportes = [a for a in filas if not es_canonico(a)]
    por_sha: dict[str, list[AttachmentFile]] = defaultdict(list)
    for a in aportes:
        if tiene_archivo(a):
            por_sha[a.sha256].append(a)
    corroboradas = {sha for sha, grupo in por_sha.items() if _corroborada(grupo, personas)}
    con_extension = {
        sha
        for sha, grupo in por_sha.items()
        if any(a.source == AttachmentFileSource.EXTENSION for a in grupo)
    }
    vigente = _version_vigente(canonicos)
    # Solo cuentan las versiones respaldadas: una subida suelta no bloquea a nadie
    # ni se entera de las demás.
    respaldadas = corroboradas | con_extension | ({vigente} if vigente else set())
    ganador = _elegir_ganador(vigente, corroboradas, con_extension)
    en_conflicto = ganador is None and len(respaldadas) > 1

    def confianza(a: AttachmentFile) -> AttachmentTrust:
        if not tiene_archivo(a):
            return AttachmentTrust.PENDING
        if ganador is not None:
            return (
                AttachmentTrust.CORROBORATED
                if a.sha256 == ganador
                else AttachmentTrust.REJECTED
            )
        if en_conflicto and a.sha256 in respaldadas:
            return AttachmentTrust.CONFLICT
        return AttachmentTrust.PENDING

    def estado(c: AttachmentFile) -> EstadoCanonico:
        if ganador is not None and c.sha256 == ganador:
            return EstadoCanonico(AttachmentVisibility.SHARED, AttachmentTrust.CORROBORATED)
        if en_conflicto and c.sha256 == vigente:
            return EstadoCanonico(AttachmentVisibility.PRIVATE, AttachmentTrust.CONFLICT)
        return EstadoCanonico(AttachmentVisibility.PRIVATE, AttachmentTrust.REJECTED)

    hay_canonica = ganador is not None and any(c.sha256 == ganador for c in canonicos)
    return DecisionDeConfianza(
        ganador=ganador,
        en_conflicto=en_conflicto,
        aportes={a.id: confianza(a) for a in aportes},
        canonicos={c.id: estado(c) for c in canonicos},
        crear_canonico=ganador if ganador is not None and not hay_canonica else None,
    )


def fuentes_para_copiar(archivos: Iterable[AttachmentFile], sha256: str) -> list[AttachmentFile]:
    """De dónde copiar la versión ganadora: primero la extensión, después la más antigua."""
    candidatas = [
        a
        for a in archivos
        if not es_canonico(a) and a.sha256 == sha256 and tiene_archivo(a)
    ]
    return sorted(
        candidatas,
        key=lambda a: (
            a.source != AttachmentFileSource.EXTENSION,
            a.completed_at or a.created_at,
            str(a.id),
        ),
    )
