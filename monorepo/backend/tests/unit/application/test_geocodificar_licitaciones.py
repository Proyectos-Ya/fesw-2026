"""Cola de geocodificación de las direcciones de entrega (HU-22, #314).

Por cada licitación pendiente se busca primero la dirección con su comuna y
región; si no aparece, la comuna sola (punto aproximado). Sin comuna y sin
resultado se marca `no_encontrada`, sin coordenadas: no se inventa una
ubicación. La caché evita repetir consultas, también las que no encontraron
nada.
"""

from uuid import UUID, uuid4

from app.application.repositories.tender_geocoding_repository import (
    ITenderGeocodingRepository,
)
from app.application.services.geocoding_service import IGeocodingService
from app.application.use_cases.tender.geocode_pending_tenders import (
    GeocodePendingTendersUseCase,
    geocoding_query,
)
from app.domain.entities.tender_map import (
    CachedGeocode,
    GeoPoint,
    GeoPrecision,
    PendingGeocoding,
)
from app.domain.errors.geocoding_errors import GeocodingUnavailable

ANCUD = GeoPoint(lat=-41.87, lng=-73.82)
YERBAS_BUENAS = GeoPoint(lat=-41.8697, lng=-73.8203)


class FakeGeocodingRepository(ITenderGeocodingRepository):
    def __init__(self, pending: list[PendingGeocoding]) -> None:
        self.pending = pending
        self.saved: dict[UUID, tuple[GeoPoint | None, GeoPrecision]] = {}
        self.cache_rows: dict[str, GeoPoint | None] = {}
        self.pedidos_limite: list[int] = []

    async def list_pending(self, limit: int) -> list[PendingGeocoding]:
        self.pedidos_limite.append(limit)
        return self.pending[:limit]

    async def save_location(
        self, tender_id: UUID, point: GeoPoint | None, precision: GeoPrecision
    ) -> None:
        self.saved[tender_id] = (point, precision)

    async def get_cached(self, query: str) -> CachedGeocode | None:
        if query not in self.cache_rows:
            return None
        return CachedGeocode(point=self.cache_rows[query])

    async def cache(self, query: str, point: GeoPoint | None) -> None:
        self.cache_rows[query] = point


class FakeGeocoder(IGeocodingService):
    def __init__(self, respuestas: dict[str, GeoPoint | None] | None = None) -> None:
        self.respuestas = respuestas or {}
        self.consultas: list[str] = []
        self.caido = False

    async def geocode(self, query: str) -> GeoPoint | None:
        self.consultas.append(query)
        if self.caido:
            raise GeocodingUnavailable("caído")
        return self.respuestas.get(query)


def _pendiente(
    direccion: str = "Yerbas Buenas #915",
    comuna: str | None = "Ancud",
    region: str | None = "Los Lagos",
) -> PendingGeocoding:
    return PendingGeocoding(
        tender_id=uuid4(), delivery_address=direccion, commune=comuna, region=region
    )


def _caso(repo, geocoder, lote: int = 10) -> GeocodePendingTendersUseCase:
    return GeocodePendingTendersUseCase(repo=repo, geocoder=geocoder, batch_size=lote)


class TestConsulta:
    def test_une_las_partes_y_agrega_chile(self):
        assert (
            geocoding_query("Yerbas Buenas #915", "Ancud", "Los Lagos")
            == "Yerbas Buenas #915, Ancud, Los Lagos, Chile"
        )

    def test_omite_las_partes_ausentes(self):
        assert geocoding_query(None, "Ancud", "Los Lagos") == "Ancud, Los Lagos, Chile"
        assert geocoding_query("Freire 5", None, None) == "Freire 5, Chile"

    def test_normaliza_espacios_para_que_la_cache_reconozca_la_misma(self):
        assert geocoding_query("  Yerbas   Buenas  #915 ", "Ancud", None) == (
            "Yerbas Buenas #915, Ancud, Chile"
        )


async def test_la_direccion_encontrada_queda_con_precision_de_direccion():
    pendiente = _pendiente()
    repo = FakeGeocodingRepository([pendiente])
    geocoder = FakeGeocoder(
        {"Yerbas Buenas #915, Ancud, Los Lagos, Chile": YERBAS_BUENAS}
    )

    resultado = await _caso(repo, geocoder).execute()

    assert resultado.ubicadas == 1
    assert repo.saved[pendiente.tender_id] == (YERBAS_BUENAS, GeoPrecision.DIRECCION)


async def test_sin_la_direccion_cae_a_la_comuna_como_aproximada():
    pendiente = _pendiente()
    repo = FakeGeocodingRepository([pendiente])
    geocoder = FakeGeocoder({"Ancud, Los Lagos, Chile": ANCUD})

    await _caso(repo, geocoder).execute()

    assert repo.saved[pendiente.tender_id] == (ANCUD, GeoPrecision.COMUNA)
    assert geocoder.consultas == [
        "Yerbas Buenas #915, Ancud, Los Lagos, Chile",
        "Ancud, Los Lagos, Chile",
    ]


async def test_sin_comuna_y_sin_resultado_no_inventa_una_ubicacion():
    pendiente = _pendiente(comuna=None)
    repo = FakeGeocodingRepository([pendiente])
    geocoder = FakeGeocoder()

    await _caso(repo, geocoder).execute()

    assert repo.saved[pendiente.tender_id] == (None, GeoPrecision.NO_ENCONTRADA)
    # Sin comuna no hay respaldo que consultar: la región sola no es un punto.
    assert geocoder.consultas == ["Yerbas Buenas #915, Los Lagos, Chile"]


async def test_sin_resultado_en_ninguna_queda_no_encontrada():
    pendiente = _pendiente()
    repo = FakeGeocodingRepository([pendiente])

    await _caso(repo, FakeGeocoder()).execute()

    assert repo.saved[pendiente.tender_id] == (None, GeoPrecision.NO_ENCONTRADA)


async def test_la_cache_responde_sin_llamar_al_servicio():
    pendiente = _pendiente()
    repo = FakeGeocodingRepository([pendiente])
    repo.cache_rows["Yerbas Buenas #915, Ancud, Los Lagos, Chile"] = YERBAS_BUENAS
    geocoder = FakeGeocoder()

    await _caso(repo, geocoder).execute()

    assert geocoder.consultas == []
    assert repo.saved[pendiente.tender_id] == (YERBAS_BUENAS, GeoPrecision.DIRECCION)


async def test_un_no_encontrado_en_cache_tampoco_se_vuelve_a_preguntar():
    pendiente = _pendiente()
    repo = FakeGeocodingRepository([pendiente])
    repo.cache_rows["Yerbas Buenas #915, Ancud, Los Lagos, Chile"] = None
    geocoder = FakeGeocoder({"Ancud, Los Lagos, Chile": ANCUD})

    await _caso(repo, geocoder).execute()

    assert geocoder.consultas == ["Ancud, Los Lagos, Chile"]
    assert repo.saved[pendiente.tender_id] == (ANCUD, GeoPrecision.COMUNA)


async def test_lo_consultado_queda_en_la_cache_tambien_sin_resultado():
    repo = FakeGeocodingRepository([_pendiente()])

    await _caso(repo, FakeGeocoder({"Ancud, Los Lagos, Chile": ANCUD})).execute()

    assert repo.cache_rows == {
        "Yerbas Buenas #915, Ancud, Los Lagos, Chile": None,
        "Ancud, Los Lagos, Chile": ANCUD,
    }


async def test_con_el_servicio_caido_corta_el_lote_y_deja_todo_pendiente():
    repo = FakeGeocodingRepository([_pendiente(), _pendiente()])
    geocoder = FakeGeocoder()
    geocoder.caido = True

    resultado = await _caso(repo, geocoder).execute()

    assert resultado.ubicadas == 0
    assert repo.saved == {}
    assert repo.cache_rows == {}
    # Una sola llamada: insistir con el servicio caído solo gasta la cuota.
    assert len(geocoder.consultas) == 1


async def test_pide_a_la_cola_solo_el_tamano_del_lote():
    repo = FakeGeocodingRepository([_pendiente() for _ in range(5)])

    resultado = await _caso(repo, FakeGeocoder(), lote=3).execute()

    assert repo.pedidos_limite == [3]
    assert resultado.ubicadas == 3


class TestContadores:
    """Con la cuota de Nominatim tan ajustada hay que poder ver si la caché sirve."""

    async def test_separa_las_consultas_de_red_de_los_aciertos_de_cache(self):
        repo = FakeGeocodingRepository([_pendiente(), _pendiente()])
        geocoder = FakeGeocoder(
            {"Yerbas Buenas #915, Ancud, Los Lagos, Chile": YERBAS_BUENAS}
        )

        resultado = await _caso(repo, geocoder).execute()

        assert resultado.ubicadas == 2
        # La segunda repite dirección: la resuelve la caché sin salir a la red.
        assert resultado.consultas == 1
        assert resultado.cacheadas == 1

    async def test_el_respaldo_por_comuna_cuenta_como_dos_consultas(self):
        repo = FakeGeocodingRepository([_pendiente()])
        geocoder = FakeGeocoder({"Ancud, Los Lagos, Chile": ANCUD})

        resultado = await _caso(repo, geocoder).execute()

        assert (resultado.consultas, resultado.cacheadas) == (2, 0)

    async def test_con_el_servicio_caido_no_cuenta_la_consulta_que_fallo(self):
        repo = FakeGeocodingRepository([_pendiente()])
        geocoder = FakeGeocoder()
        geocoder.caido = True

        resultado = await _caso(repo, geocoder).execute()

        assert (resultado.ubicadas, resultado.consultas) == (0, 0)
