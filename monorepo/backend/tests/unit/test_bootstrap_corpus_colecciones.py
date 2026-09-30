"""La carga inicial tiene que dejar lista cada colección en la que escribe la ingesta.

`bootstrap_corpus` existe para entornos donde la aplicación nunca corrió, y es la
aplicación (`main.py`) la que crea las colecciones de Qdrant al arrancar. Desde
que la ingesta guarda también un multivector por licitación en `tender_items`,
una carga sobre un Qdrant vacío fallaba en cada licitación con "collection not
found", y tras tres intentos las daba por perdidas.
"""

from unittest.mock import MagicMock

from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
    QdrantTenderItemVectorRepository,
)
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from scripts import bootstrap_corpus


async def test_prepara_la_coleccion_de_partidas_ademas_de_la_de_licitaciones(
    monkeypatch,
):
    import app.infrastructure.seeder as seeder

    preparadas: list[str] = []

    class SesionFalsa:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc) -> None: ...

    async def sembrar(_session) -> None: ...

    async def ensure_licitaciones(_self) -> None:
        preparadas.append("tenders")

    async def ensure_partidas(_self) -> None:
        preparadas.append("tender_items")

    monkeypatch.setattr(bootstrap_corpus, "AsyncSession", lambda _engine: SesionFalsa())
    monkeypatch.setattr(seeder, "seed_database_metadata", sembrar)
    monkeypatch.setattr(QdrantTenderRepository, "ensure_collection", ensure_licitaciones)
    monkeypatch.setattr(
        QdrantTenderItemVectorRepository, "ensure_collection", ensure_partidas
    )

    await bootstrap_corpus._preparar_destino(MagicMock(), MagicMock())

    assert sorted(preparadas) == ["tender_items", "tenders"]
