from abc import ABC, abstractmethod
from uuid import UUID

from app.application.schemas.tender_schema import TenderFilterCriteria


class ITenderItemVectorRepository(ABC):
    """
    Interfaz abstracta para el repositorio vectorial de las partidas (ítems) de
    las licitaciones.

    Guarda, por licitación, un vector por cada partida. Permite calcular el calce
    entre las keywords del proveedor y cada partida en vez de comparar contra el
    texto agregado de toda la licitación, y recuperar licitaciones cuyas partidas
    calzan con las keywords (segundo canal de recuperación, junto al vector de la
    licitación completa).

    Cada punto lleva el mismo payload que el de la licitación en la colección
    "tenders" (estado, región, provincia, comuna, monto, cierre, publicación), de
    modo que la búsqueda pueda pre-filtrar con los mismos criterios.
    """

    @abstractmethod
    async def upsert(
        self,
        tender_id: UUID,
        item_vectors: list[list[float]],
        payload: dict | None = None,
    ) -> None:
        """
        Reemplaza todos los vectores de partidas de una licitación, y su payload.

        Reemplaza el punto entero: el payload que ya tuviera se descarta, así que
        quien reescribe los vectores debe volver a entregar el payload completo.
        Sin payload el punto no pasa ningún filtro de la búsqueda por keywords.

        Con una lista vacía elimina lo guardado: una licitación sin partidas no
        tiene vectores.
        """
        ...

    @abstractmethod
    async def set_payload(self, tender_id: UUID, payload: dict) -> None:
        """
        Actualiza campos del payload sin tocar los vectores.

        Es la operación barata para un cambio de estado, plazo o monto: no cambia
        lo que la licitación pide, así que no hay por qué releer ni recalcular sus
        vectores. Actualiza solo las claves entregadas; las demás se conservan.

        No hace nada si la licitación no tiene vectores de partidas guardados
        (por ejemplo, una ingestada antes de existir esta colección y aún sin
        backfill): no crea un punto sin vectores ni falla.
        """
        ...

    @abstractmethod
    async def get_many(self, tender_ids: list[UUID]) -> dict[UUID, list[list[float]]]:
        """
        Devuelve los vectores de partidas de las licitaciones pedidas.

        Solo incluye las licitaciones que tienen vectores; las que faltan
        simplemente no aparecen en el diccionario.
        """
        ...

    @abstractmethod
    async def delete(self, tender_id: UUID) -> None:
        """
        Elimina los vectores de partidas de una licitación.
        """
        ...

    @abstractmethod
    async def search_by_keywords(
        self,
        keyword_vectors: list[list[float]],
        limit: int,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:
        """
        Busca las licitaciones cuyas partidas mejor calzan con las keywords.

        El puntaje de una licitación es MaxSim: por cada keyword se toma el mejor
        coseno contra sus partidas y se suman (Σ_keywords max_partidas coseno). Una
        licitación con una sola partida muy afín a cada keyword puntúa alto aunque
        el resto de su texto no tenga relación.

        Los criterios se aplican como pre-filtro DENTRO de la búsqueda, con la
        misma interpretación que en la colección de licitaciones: filtrar después
        del top-K devolvería casi nada cuando el filtro es específico.

        Devuelve tuplas (tender_id, puntaje) ordenadas por puntaje descendente, a
        lo más `limit`; lista vacía si no hay keywords.
        """
        ...
