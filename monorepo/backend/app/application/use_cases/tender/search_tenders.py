from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.repositories.tender_repository import (
    ClosingOrder,
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
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.errors.tender_errors import InvalidSearchCriteria
from app.shared.constants import ACTIVE_TENDER_STATUSES, TENDER_STATUS_CODE_BY_ID
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

# Estados por los que se puede filtrar: los que tienen un `id_estado` medido.
# `proveedor_seleccionado` y `oc_emitida` no lo tienen (ver constants.py), así
# que en SQL no hay con qué compararlos y aceptarlos devolvería cero en silencio.
FILTERABLE_STATUS_CODES = frozenset(TENDER_STATUS_CODE_BY_ID.values())


class SearchTendersUseCase:
    """Búsqueda manual de licitaciones con filtros absolutos.

    Hay dos caminos, y el que se usa lo deciden el texto y el **estado**
    seleccionado:

    - **Qdrant**, ordenado por afinidad con el vector de la empresa: solo sin
      texto y cuando la selección de estado es únicamente activa (`publicada`).
      El índice vectorial guarda solo vigentes, así que es el único caso en que
      contiene todo lo que se pidió.
    - **Postgres** para todo lo demás: con texto (búsqueda léxica, ordenada por
      relevancia de texto), sin filtro de estado (que significa "todos") o con
      cualquier estado no activo. Sin texto, ordena por cierre: lo más próximo
      a cerrar si son vigentes, lo que cerró más recientemente si entran
      cerradas.

    En los dos, los filtros se aplican **dentro** de la búsqueda, no sobre el
    resultado.

    Si el proveedor todavía no tiene vector —recién registrado, perfil sin
    completar— no hay con qué ordenar por afinidad y se cae al camino SQL,
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
        supplier_id: UUID | None = None,
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

        solo_activas = self._solo_estados_activos(criteria)
        orden = ClosingOrder.ASC if solo_activas else ClosingOrder.DESC

        has_text_query = bool(q and q.strip())
        if has_text_query:
            sanitized_q = sanitize_search_query(q)
            if not sanitized_q:
                return TenderSearchResult(
                    items=[],
                    total=0,
                    is_truncated=False,
                )
            return await self._search_in_sql(
                criteria, effective_limit, offset, orden, q=sanitized_q
            )

        # Qdrant solo guarda vigentes: con cualquier otro estado en juego, lo
        # que falta del índice haría que el resultado saliera incompleto.
        if not solo_activas:
            return await self._search_in_sql(criteria, effective_limit, offset, orden)

        vector = await self._resolve_vector(user_id, "", supplier_id=supplier_id)
        if vector is None:
            return await self._search_in_sql(criteria, effective_limit, offset, orden)

        hits = await self.tender_vector_repo.search_by_vector(
            vector=vector,
            limit=effective_limit,
            offset=offset,
            criteria=criteria,
        )
        if not hits:
            return TenderSearchResult(
                items=[],
                total=0,
                is_truncated=False,
            )

        total = await self.tender_vector_repo.count(criteria)
        ids_en_orden = [tender_id for tender_id, _ in hits]
        # Preserva el orden de similitud que dio Qdrant
        id_a_posicion = {tender_id: i for i, tender_id in enumerate(ids_en_orden)}

        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=ids_en_orden))
        tenders_ordenadas = sorted(
            tenders, key=lambda t: id_a_posicion.get(t.id, len(ids_en_orden))
        )
        return TenderSearchResult(
            items=tenders_ordenadas,
            total=total,
            is_truncated=total > offset + len(tenders_ordenadas),
        )

    @staticmethod
    def _solo_estados_activos(criteria: TenderFilterCriteria) -> bool:
        """Si la selección de estado cabe entera en el índice vectorial.

        Sin selección no: el contrato de la API es que sin estado entra todo.
        """
        return bool(criteria.status_codes) and set(criteria.status_codes) <= (
            ACTIVE_TENDER_STATUSES
        )

    def _validate(
        self, criteria: TenderFilterCriteria, limit: int | None, offset: int
    ) -> None:
        """Falla rápido ante rangos invertidos o valores que no tienen sentido.

        Un rango donde desde > hasta devolvería 0 resultados por definición en
        SQL/Qdrant, pero avisar con 422 es más útil que dejar que se interprete
        como "no hay licitaciones" en vez de "escribiste el filtro al revés".
        Los extremos iguales sí son válidos: los límites son inclusivos.
        """
        if offset < 0:
            raise InvalidSearchCriteria("El desplazamiento no puede ser negativo.")

        if limit is not None and limit < 1:
            raise InvalidSearchCriteria("El límite debe ser al menos 1.")

        desconocidos = set(criteria.status_codes or []) - FILTERABLE_STATUS_CODES
        if desconocidos:
            raise InvalidSearchCriteria(
                f"Estado desconocido: {', '.join(sorted(desconocidos))}. "
                f"Los válidos son: {', '.join(sorted(FILTERABLE_STATUS_CODES))}."
            )

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
        self, user_id: UUID, query_text: str, supplier_id: UUID | None = None
    ) -> list[float] | None:
        """El texto manda; sin texto, el perfil del proveedor."""
        if query_text:
            vectors = await self.embedding_service.embed([query_text])
            return vectors[0]

        supplier = await resolver_empresa(self.supplier_repo, user_id, supplier_id)
        if supplier is None:
            return None
        return await self.supplier_vector_repo.get_vector(supplier.id)

    async def _search_in_sql(
        self,
        criteria: TenderFilterCriteria,
        limit: int,
        offset: int,
        closing_order: ClosingOrder,
        q: str | None = None,
    ) -> TenderSearchResult:
        items, total = await self.tender_repo.search_tenders(
            criteria=criteria,
            limit=limit,
            offset=offset,
            q=q,
            closing_order=closing_order,
        )
        return TenderSearchResult(
            items=items,
            total=total,
            is_truncated=total > offset + len(items),
        )
