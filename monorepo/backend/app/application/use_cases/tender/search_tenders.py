from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.schemas.tender_schema import (
    TenderFilterCriteria,
    TenderSearchResult,
)
from app.application.services.embedding_service import IEmbeddingService
from app.domain.entities.tender import Tender
from app.domain.errors.tender_errors import InvalidSearchCriteria
from app.shared.search_sanitizer import sanitize_search_query

# Tope de resultados por petición. Con la semántica no existe un corte natural:
# toda licitación tiene algún grado de similitud con la consulta, así que "todos
# los resultados" serían las miles elegibles, incluida la última que no tiene
# nada que ver. El tope acota el payload —cada licitación son ~1,5 KB con sus
# ítems— y solo se alcanza cuando el usuario prácticamente no filtró, que es
# justo el caso donde pedirle que acote es lo correcto.
DEFAULT_RESULT_LIMIT = 100

# Tope absoluto por petición. A mayor profundidad, Qdrant recupera y ordena
# `offset + limit` para descartar los primeros, así que el costo crece; y cada
# licitación pesa ~1,5 KB con sus ítems.
MAX_RESULT_LIMIT = 500


class SearchTendersUseCase:
    """Búsqueda manual de licitaciones: semántica con filtros absolutos.

    Los filtros se aplican **dentro** de la búsqueda vectorial, no sobre el
    resultado. El orden lo da la similitud con un vector, y de dónde sale ese
    vector es lo único que distingue los dos modos:

    - con texto: se embebe la consulta del usuario
    - sin texto: se usa el vector del propio proveedor, de modo que los filtros
      acotan y la afinidad con la empresa ordena

    Si el proveedor todavía no tiene vector —recién registrado, perfil sin
    completar— no hay con qué ordenar por relevancia y se cae al camino SQL,
    ordenado por fecha de cierre. Es un respaldo para no dejar sin buscador a
    quien acaba de llegar, no un modo paralelo.

    Una caída de Qdrant **no** se atrapa acá: el criterio de aceptación pide
    avisar que la búsqueda no se pudo completar, no devolver resultados sin
    ranking sin decírselo al usuario. El error sube y el router lo traduce.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        supplier_vector_repo: ISupplierVectorRepository,
        tender_vector_repo: ITenderVectorRepository,
        tender_repo: ITenderRepository,
        embedding_service: IEmbeddingService,
        result_limit: int = DEFAULT_RESULT_LIMIT,
        max_result_limit: int = MAX_RESULT_LIMIT,
    ) -> None:
        self.supplier_repo = supplier_repo
        self.supplier_vector_repo = supplier_vector_repo
        self.tender_vector_repo = tender_vector_repo
        self.tender_repo = tender_repo
        self.embedding_service = embedding_service
        self.result_limit = result_limit
        self.max_result_limit = max_result_limit

    async def execute(
        self,
        user_id: UUID,
        q: str | None = None,
        criteria: TenderFilterCriteria | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> TenderSearchResult:
        criteria = criteria or TenderFilterCriteria()
        self._validate(criteria, limit, offset)
        # El recorte no depende de que el borde HTTP valide bien: es una defensa
        # de recursos, y pedir 5.000 no puede traducirse en 5.000 hidrataciones.
        effective_limit = min(
            limit if limit is not None else self.result_limit, self.max_result_limit
        )

        has_text_query = bool(q and q.strip())
        if has_text_query:
            sanitized_q = sanitize_search_query(q)
            if not sanitized_q:
                return TenderSearchResult(
                    items=[],
                    total=0,
                    is_truncated=False,
                )

            items, total = await self.tender_repo.search_tenders(
                criteria=criteria,
                limit=effective_limit,
                offset=offset,
                q=sanitized_q,
            )
            return TenderSearchResult(
                items=items,
                total=total,
                is_truncated=total > offset + len(items),
            )

        vector = await self._resolve_vector(user_id, "")
        if vector is None:
            return await self._search_without_ranking(criteria, effective_limit, offset)

        hits = await self.tender_vector_repo.search_by_vector(
            vector=vector,
            limit=effective_limit,
            offset=offset,
            criteria=criteria,
        )
        total = await self.tender_vector_repo.count(criteria)
        items = await self._hydrate(hits)

        return TenderSearchResult(
            items=items,
            total=total,
            is_truncated=total > offset + len(hits),
        )

    @staticmethod
    def _validate(
        criteria: TenderFilterCriteria, limit: int | None, offset: int
    ) -> None:
        """Rechaza criterios que no pueden cumplirse.

        Un rango invertido devolvería una lista vacía, y el usuario la leería
        como "no hay licitaciones" en vez de "escribiste el filtro al revés".
        Los extremos iguales sí son válidos: los límites son inclusivos.
        """
        if offset < 0:
            raise InvalidSearchCriteria("El desplazamiento no puede ser negativo.")

        if limit is not None and limit < 1:
            raise InvalidSearchCriteria("El límite debe ser al menos 1.")

        rangos_de_fecha = (
            ("cierre", criteria.closing_from, criteria.closing_to),
            ("publicación", criteria.published_from, criteria.published_to),
        )
        for nombre, desde, hasta in rangos_de_fecha:
            if desde is not None and hasta is not None and desde > hasta:
                raise InvalidSearchCriteria(
                    f"El rango de {nombre} está invertido: "
                    f"la fecha inicial es posterior a la final."
                )

        for nombre, monto in (
            ("mínimo", criteria.min_amount),
            ("máximo", criteria.max_amount),
        ):
            if monto is not None and monto < 0:
                raise InvalidSearchCriteria(f"El monto {nombre} no puede ser negativo.")

        if (
            criteria.min_amount is not None
            and criteria.max_amount is not None
            and criteria.min_amount > criteria.max_amount
        ):
            raise InvalidSearchCriteria(
                "El rango de monto está invertido: el mínimo supera al máximo."
            )

    async def _resolve_vector(
        self, user_id: UUID, query_text: str
    ) -> list[float] | None:
        """El texto manda; sin texto, el perfil del proveedor."""
        if query_text:
            vectors = await self.embedding_service.embed([query_text])
            return vectors[0]

        supplier = await self.supplier_repo.get_by_user_id(user_id)
        if supplier is None:
            return None
        return self.supplier_vector_repo.get_vector(supplier.id)

    async def _search_without_ranking(
        self, criteria: TenderFilterCriteria, limit: int, offset: int
    ) -> TenderSearchResult:
        """Sin vector no hay relevancia que calcular: se ordena por fecha de cierre."""
        items, total = await self.tender_repo.search_tenders(
            criteria=criteria, limit=limit, offset=offset
        )
        return TenderSearchResult(
            items=items,
            total=total,
            is_truncated=total > offset + len(items),
        )

    async def _hydrate(self, hits: list[tuple[UUID, float]]) -> list[Tender]:
        """Trae las licitaciones desde SQL conservando el orden del ranking.

        Qdrant devuelve `(id, score)` y `get_tenders` no garantiza orden, así que
        reordenar acá es obligatorio: perder el orden dejaría la lista sin
        ordenar por relevancia sin que nada fallara.

        Los ids sin fila en SQL se omiten. Ese desbalance existe y está
        documentado (`rank_tenders`, paso 3.3.1); en una búsqueda se prefiere una
        lista más corta a una con huecos.
        """
        if not hits:
            return []

        ids = [tender_id for tender_id, _ in hits]
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=ids))
        by_id = {t.id: t for t in tenders}
        return [by_id[tender_id] for tender_id in ids if tender_id in by_id]
