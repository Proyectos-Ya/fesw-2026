"""Construcción, al arrancar, de los servicios con proveedor configurable."""

import logging

from app.application.services.calendar_provider_client import ICalendarProviderClient
from app.application.services.company_lookup_service import ICompanyLookupService
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.reranker_service import IRerankerService
from app.config import settings
from app.domain.entities.calendar import CalendarProvider
from app.infrastructure.services.api_embedding_service import (
    ApiEmbeddingService,
    DeepInfraEmbeddingService,
    HuggingFaceEmbeddingService,
)
from app.infrastructure.services.api_reranker_service import ApiRerankerService
from app.infrastructure.services.calendar.google_calendar_client import (
    GoogleCalendarClient,
)
from app.infrastructure.services.company_lookup.http_company_lookup_service import (
    HttpCompanyLookupService,
    SreLookupService,
    WebEmpresarioLookupService,
)

logger = logging.getLogger(__name__)


def build_calendar_providers() -> dict[CalendarProvider, ICalendarProviderClient]:
    """Solo los proveedores con credenciales; sin ninguno, la sincronización queda apagada."""
    providers: dict[CalendarProvider, ICalendarProviderClient] = {}
    if settings.google_calendar_client_id and settings.google_calendar_client_secret:
        providers[CalendarProvider.GOOGLE] = GoogleCalendarClient(
            client_id=settings.google_calendar_client_id,
            client_secret=settings.google_calendar_client_secret,
            redirect_uri=settings.google_calendar_redirect_uri,
        )
    return providers


class MockRerankerService(IRerankerService):
    """Reranker neutro para cuando está desactivado o falta ONNX en local/tests."""

    async def rerank(self, query_text, candidates, limit):
        return [(c[0], 1.0) for c in candidates][:limit]


class MockEmbeddingService(IEmbeddingService):
    """Embeddings en cero, para levantar en local sin el modelo descargado.

    Con él toda búsqueda y todo matching devuelven resultados sin sentido, y la
    aplicación se ve perfectamente sana desde afuera. Por eso vive solo en
    desarrollo y grita en los logs.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * settings.embedding_vector_size for _ in texts]


# Cada proveedor habla su propio dialecto HTTP; el mapa evita un if por cada uno.
# Los valores posibles los acota el Literal de `Settings.embedding_provider`, así que
# una clave faltante es un error de programación, no de configuración.
_EMBEDDING_POR_PROVEEDOR: dict[str, type[ApiEmbeddingService]] = {
    "deepinfra": DeepInfraEmbeddingService,
    "huggingface": HuggingFaceEmbeddingService,
}


def build_embedding_service() -> IEmbeddingService:
    """Construye el servicio de embeddings según el proveedor configurado.

    Mismo criterio que el reranker, y por la misma razón: antes esto caía a
    `MockEmbeddingService` con un `logger.warning` incluso en producción. Un
    despliegue donde el modelo no carga quedaba "exitoso", respondiendo con
    vectores de puros ceros —y peor, la ingesta los escribía en Qdrant, que no
    se arregla corrigiendo la configuración: hay que reindexar.
    """
    if settings.embedding_provider != "local":
        logger.info(
            "Embeddings servidos por %s (%s).",
            settings.embedding_provider,
            settings.embedding_model,
        )
        return _EMBEDDING_POR_PROVEEDOR[settings.embedding_provider](
            api_key=settings.embedding_api_key or "",
            base_url=settings.embedding_api_url,
            model_name=settings.embedding_model,
        )

    try:
        # Importación tardía: sentence-transformers no está en la imagen de
        # producción cuando se corre en modo API.
        from app.infrastructure.services.bge_m3_embedding_service import (
            BgeM3EmbeddingService,
        )

        return BgeM3EmbeddingService(model_name=settings.embedding_model)
    except Exception as exc:
        if not settings.is_dev:
            logger.exception(
                "El servicio de embeddings no se pudo construir (%s) y "
                "IS_DEV=false, así que la aplicación no arranca. Degradarse en "
                "silencio serviría búsquedas y matching sin ningún sentido.",
                exc,
            )
            raise

        logger.exception(
            "El servicio de embeddings no se pudo construir (%s). Se continúa "
            "con MockEmbeddingService porque IS_DEV=true, pero las búsquedas y "
            "el matching no tienen sentido hasta que esto se resuelva.",
            exc,
        )
        return MockEmbeddingService()


def build_reranker_service() -> IRerankerService:
    """Construye el reranker, o decide qué hacer si no se puede.

    `MockRerankerService` devuelve 1.0 para todas las candidatas: con él la
    aplicación responde igual, pero el orden de las recomendaciones es
    arbitrario. Es una degradación que no se nota desde afuera, así que la
    única defensa es que quede escrita en los logs.

    Por eso el fallback vive solo en desarrollo. Fuera de ahí un reranker que
    no arranca es un fallo de arranque: mejor no levantar que servir
    recomendaciones en orden aleatorio sin que nadie se entere.
    """
    if settings.disable_reranker:
        logger.warning(
            "Reranker desactivado por configuración (DISABLE_RERANKER). "
            "Se usa MockRerankerService y las recomendaciones no van ordenadas."
        )
        return MockRerankerService()

    if settings.reranker_provider != "local":
        # Sin try/except: config.py ya garantizó que hay credencial, y construir
        # el cliente no toca la red. Un fallo acá sería un error de programación,
        # no una condición del entorno que tenga sentido absorber.
        logger.info("Reranker servido por API (%s).", settings.pinecone_rerank_model)
        return ApiRerankerService(
            api_key=settings.pinecone_api_key or "",
            base_url=settings.pinecone_base_url,
            model_name=settings.pinecone_rerank_model,
            api_version=settings.pinecone_api_version,
        )

    try:
        # Importación tardía: arrastra onnxruntime y transformers, que en modo
        # API no están instalados en la imagen.
        from app.infrastructure.services.bge_reranker_service import (
            BgeRerankerService,
        )

        return BgeRerankerService()
    except Exception as exc:
        # En producción no se traga: relanza y el arranque falla con la traza.
        if not settings.is_dev:
            logger.exception(
                "El reranker no se pudo construir (%s) y IS_DEV=false, así que "
                "la aplicación no arranca. Degradarse en silencio serviría "
                "recomendaciones en orden arbitrario.",
                exc,
            )
            raise

        # En local sí: falta de RAM u ONNX no debería impedir levantar la API.
        logger.exception(
            "El reranker no se pudo construir (%s). Se continúa con "
            "MockRerankerService porque IS_DEV=true, pero las recomendaciones "
            "van en orden arbitrario hasta que esto se resuelva.",
            exc,
        )
        return MockRerankerService()


_FUENTE_DE_EMPRESAS_POR_PROVEEDOR: dict[str, type[HttpCompanyLookupService]] = {
    "sre": SreLookupService,
    "web-empresario": WebEmpresarioLookupService,
}


def build_company_lookup_service() -> ICompanyLookupService | None:
    """Fuente de datos de empresas para importar el perfil por RUT (HdU 16).

    Sin fuente configurada devuelve `None` y la importación queda apagada: es una
    ayuda del wizard, no algo de lo que dependa crear la empresa. La credencial ya
    la exigió `config.py` y construir el cliente no toca la red.
    """
    if settings.company_lookup_provider == "none":
        logger.info("Importación de perfil por RUT desactivada (COMPANY_LOOKUP_PROVIDER=none).")
        return None

    logger.info("Importación de perfil por RUT servida por %s.", settings.company_lookup_provider)
    return _FUENTE_DE_EMPRESAS_POR_PROVEEDOR[settings.company_lookup_provider](
        api_key=settings.company_lookup_api_key or "",
        base_url=settings.company_lookup_url,
    )
