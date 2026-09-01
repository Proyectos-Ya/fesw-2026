"""El seeder debe poblar exactamente la numeración de `CHILE_REGIONS`.

Además tiene que **corregir** una fila existente cuyo nombre no corresponda: las
bases creadas antes de unificar la numeración tienen los 16 ids con los nombres
equivocados, y el seeder es el único punto por el que pasan todos los arranques.
"""

from typing import Any

from app.infrastructure.repositories.tender_model import RegionModel, TenderStatusModel
from app.infrastructure.seeder import seed_database_metadata
from app.shared.constants import TENDER_STATUS_CODE_BY_ID
from app.shared.regions import CHILE_REGIONS, UNKNOWN_REGION_ID


class _FakeResult:
    def __init__(self, value: Any = None) -> None:
        self._value = value

    def first(self) -> Any:
        return self._value


class FakeSession:
    """Sesión mínima: registra los `add` y responde `get`/`exec` desde memoria."""

    def __init__(self, existing_regions: dict[int, RegionModel] | None = None) -> None:
        self.existing_regions = existing_regions or {}
        self.added: list[Any] = []
        self.committed = False

    async def get(self, model: type, pk: int) -> Any:  # noqa: ARG002
        return self.existing_regions.get(pk)

    async def exec(self, statement: Any) -> _FakeResult:  # noqa: ARG002
        return _FakeResult(None)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True


def _regions_added(session: FakeSession) -> dict[int, str]:
    return {r.id: r.name for r in session.added if isinstance(r, RegionModel)}


class TestSeedRegions:
    async def test_siembra_exactamente_chile_regions(self):
        session = FakeSession()

        await seed_database_metadata(session)  # type: ignore[arg-type]

        sembradas = _regions_added(session)
        for r_id, nombre in CHILE_REGIONS.items():
            assert sembradas[r_id] == nombre

    async def test_siembra_la_region_desconocida(self):
        session = FakeSession()

        await seed_database_metadata(session)  # type: ignore[arg-type]

        assert UNKNOWN_REGION_ID in _regions_added(session)

    async def test_no_duplica_una_region_ya_existente(self):
        existente = RegionModel(id=13, name=CHILE_REGIONS[13])
        session = FakeSession(existing_regions={13: existente})

        await seed_database_metadata(session)  # type: ignore[arg-type]

        assert 13 not in _regions_added(session)

    async def test_corrige_el_nombre_de_una_region_mal_numerada(self):
        """Una base sembrada con la numeración antigua tiene el 13 como 'Los Ríos'."""
        desactualizada = RegionModel(id=13, name="Los Ríos")
        session = FakeSession(existing_regions={13: desactualizada})

        await seed_database_metadata(session)  # type: ignore[arg-type]

        assert desactualizada.name == CHILE_REGIONS[13]

    async def test_confirma_los_cambios(self):
        session = FakeSession()

        await seed_database_metadata(session)  # type: ignore[arg-type]

        assert session.committed


class TestSeedStatuses:
    async def test_siembra_exactamente_los_estados_medidos(self):
        """Se compara contra el mapeo y no contra una lista repetida acá.

        La versión anterior fijaba {1, 2, 6, 7, 8, 18}, heredados de la API de
        Licitaciones. Al ser una cuarta copia del mapeo, cambiar la fuente no la
        hacía fallar: solo fallaba el día que alguien tocaba el seeder.
        """
        session = FakeSession()

        await seed_database_metadata(session)  # type: ignore[arg-type]

        estados = [s for s in session.added if isinstance(s, TenderStatusModel)]
        assert {s.id for s in estados} == set(TENDER_STATUS_CODE_BY_ID)

    async def test_el_nombre_se_deriva_del_codigo_semantico(self):
        session = FakeSession()

        await seed_database_metadata(session)  # type: ignore[arg-type]

        por_id = {
            s.id: s.name
            for s in session.added
            if isinstance(s, TenderStatusModel)
        }
        assert por_id[2] == "Publicada"
        assert por_id[6] == "Desierta"
