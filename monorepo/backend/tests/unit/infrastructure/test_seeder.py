"""El seeder debe poblar exactamente la numeración de `CHILE_REGIONS`.

Además tiene que **corregir** una fila existente cuyo nombre no corresponda: las
bases creadas antes de unificar la numeración tienen los 16 ids con los nombres
equivocados, y el seeder es el único punto por el que pasan todos los arranques.
"""

from typing import Any

from app.infrastructure.repositories.tender_model import (
    ComunaModel,
    ProvinciaModel,
    RegionModel,
    TenderStatusModel,
)
from app.infrastructure.seeder import seed_database_metadata
from app.shared.comunas import CHILE_COMUNAS, CHILE_PROVINCIAS
from app.shared.constants import TENDER_STATUS_CODE_BY_ID
from app.shared.regions import CHILE_REGIONS, UNKNOWN_REGION_ID

CHILE_REGION_ID_BY_NAME = {name: r_id for r_id, name in CHILE_REGIONS.items()}


class _FakeResult:
    def __init__(self, value: Any = None) -> None:
        self._value = value

    def first(self) -> Any:
        return self._value


class FakeSession:
    """Sesión mínima: registra los `add` y responde `get`/`exec` desde memoria.

    `get` distingue por tipo de modelo -- provincia y comuna también arrancan
    sus ids en 1, así que si no distinguiera devolvería una región donde se
    pidió una provincia.
    """

    def __init__(
        self,
        existing_regions: dict[int, RegionModel] | None = None,
        existing_provincias: dict[int, ProvinciaModel] | None = None,
        existing_comunas: dict[int, ComunaModel] | None = None,
    ) -> None:
        self.existing_regions = existing_regions or {}
        self.existing_provincias = existing_provincias or {}
        self.existing_comunas = existing_comunas or {}
        self.added: list[Any] = []
        self.committed = False

    async def get(self, model: type, pk: int) -> Any:
        if model is RegionModel:
            return self.existing_regions.get(pk)
        if model is ProvinciaModel:
            return self.existing_provincias.get(pk)
        if model is ComunaModel:
            return self.existing_comunas.get(pk)
        return None

    async def exec(self, statement: Any) -> _FakeResult:  # noqa: ARG002
        return _FakeResult(None)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True


def _regions_added(session: FakeSession) -> dict[int, str]:
    return {r.id: r.name for r in session.added if isinstance(r, RegionModel)}


def _provincias_added(session: FakeSession) -> dict[int, ProvinciaModel]:
    return {p.id: p for p in session.added if isinstance(p, ProvinciaModel)}


def _comunas_added(session: FakeSession) -> dict[int, ComunaModel]:
    return {c.id: c for c in session.added if isinstance(c, ComunaModel)}


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
            s.id: s.name for s in session.added if isinstance(s, TenderStatusModel)
        }
        assert por_id[2] == "Publicada"
        assert por_id[6] == "Desierta"


class TestSeedProvincias:
    async def test_siembra_las_56_provincias(self):
        session = FakeSession()

        await seed_database_metadata(session)  # type: ignore[arg-type]

        sembradas = _provincias_added(session)
        assert len(sembradas) == 56
        for p_id, (nombre, region_name) in CHILE_PROVINCIAS.items():
            assert sembradas[p_id].name == nombre
            assert sembradas[p_id].region_id == CHILE_REGION_ID_BY_NAME[region_name]

    async def test_no_duplica_una_provincia_ya_existente(self):
        nombre, region_name = CHILE_PROVINCIAS[1]
        existente = ProvinciaModel(
            id=1, name=nombre, region_id=CHILE_REGION_ID_BY_NAME[region_name]
        )
        session = FakeSession(existing_provincias={1: existente})

        await seed_database_metadata(session)  # type: ignore[arg-type]

        assert 1 not in _provincias_added(session)

    async def test_corrige_el_nombre_de_una_provincia_desactualizada(self):
        desactualizada = ProvinciaModel(id=1, name="Nombre Viejo", region_id=1)
        session = FakeSession(existing_provincias={1: desactualizada})

        await seed_database_metadata(session)  # type: ignore[arg-type]

        assert desactualizada.name == CHILE_PROVINCIAS[1][0]


class TestSeedComunas:
    async def test_siembra_las_346_comunas(self):
        session = FakeSession()

        await seed_database_metadata(session)  # type: ignore[arg-type]

        sembradas = _comunas_added(session)
        assert len(sembradas) == 346
        for c_id, (nombre, _provincia_name) in CHILE_COMUNAS.items():
            assert sembradas[c_id].name == nombre

    async def test_no_duplica_una_comuna_ya_existente(self):
        nombre, provincia_name = CHILE_COMUNAS[1]
        provincia_id = next(
            pid
            for pid, (name, _r) in CHILE_PROVINCIAS.items()
            if name == provincia_name
        )
        existente = ComunaModel(id=1, name=nombre, provincia_id=provincia_id)
        session = FakeSession(existing_comunas={1: existente})

        await seed_database_metadata(session)  # type: ignore[arg-type]

        assert 1 not in _comunas_added(session)

    async def test_corrige_el_nombre_de_una_comuna_desactualizada(self):
        desactualizada = ComunaModel(id=1, name="Nombre Viejo", provincia_id=1)
        session = FakeSession(existing_comunas={1: desactualizada})

        await seed_database_metadata(session)  # type: ignore[arg-type]

        assert desactualizada.name == CHILE_COMUNAS[1][0]
