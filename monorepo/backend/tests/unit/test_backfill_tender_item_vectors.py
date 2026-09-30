"""Las guardas y la lógica pura del backfill de vectores de partidas.

El script recorre el corpus completo, llama a un modelo pesado y escribe en
Qdrant. Lo que se prueba acá es lo que no se puede corregir después:

- que no apunte a una base o a un Qdrant remotos sin confirmación explícita;
- que no escriba vectores de puros ceros con el embedding de mentira;
- que embeba en lotes chicos y ordenados por largo (con lotes grandes BGE-M3 se
  queda sin memoria con partidas largas);
- que sea reanudable: lo que ya tiene vectores no se vuelve a embeber;
- que las partidas reciban el payload de "tenders" (para pre-filtrar por estado,
  región o plazo dentro de la búsqueda), copiándolo sin re-embeber a las que ya
  tenían vectores, y que `--solo-payload` haga solo eso sin cargar el modelo.

Nada de esto toca Postgres ni Qdrant: el lector de SQL se inyecta como función.
"""

import argparse
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bootstrap import MockEmbeddingService
from scripts.backfill_tender_item_vectors import (
    TAMANO_LOTE_EMBEDDING,
    Resumen,
    _clasificar,
    _destinos_no_locales,
    _embeber_por_lotes,
    _es_local,
    _exigir_embedding_real,
    _grupos_pendientes,
    _indexar_grupo,
    _lector_payloads,
    _lotes_por_largo,
    _repartir,
    procesar,
)
from tests.unit.application.fakes import (
    FakeEmbeddingPorTexto,
    FakeEmbeddingService,
    InMemoryTenderItemVectorRepository,
)


def _id(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


def _fuente(licitaciones: list[tuple[uuid.UUID, list[str]]]):
    """Un lector de páginas en memoria, con la misma paginación por id que el SQL."""
    ordenadas = sorted(licitaciones, key=lambda par: par[0])

    async def leer_pagina(despues_de, tamano):
        restantes = [par for par in ordenadas if despues_de is None or par[0] > despues_de]
        return restantes[:tamano]

    return leer_pagina


class TestEsLocal:
    @pytest.mark.parametrize(
        "url",
        [
            "postgresql://u:p@localhost:5432/db",
            "postgresql://u:p@127.0.0.1:5432/db",
            "postgresql://u:p@[::1]:5432/db",
            "postgresql://u:p@db:5432/db",
            "postgresql://u:p@host.docker.internal:5432/db",
            "http://localhost:6333",
        ],
    )
    def test_hosts_de_desarrollo_son_locales(self, url):
        assert _es_local(url) is True

    def test_una_base_remota_no_es_local(self):
        assert _es_local("postgresql://u:p@db.abc.supabase.co:5432/postgres") is False


class TestDestinosNoLocales:
    """Contra producción se corre a propósito, no por olvidar una variable."""

    def test_todo_local_no_pide_confirmacion(self):
        assert (
            _destinos_no_locales(
                "postgresql://u:p@localhost:5432/db", "http://localhost:6333"
            )
            == []
        )

    def test_una_base_remota_se_nombra(self):
        destinos = _destinos_no_locales(
            "postgresql://u:p@db.abc.supabase.co:5432/postgres", "http://localhost:6333"
        )

        assert len(destinos) == 1
        assert "db.abc.supabase.co" in destinos[0]

    def test_un_qdrant_remoto_tambien_cuenta_aunque_la_base_sea_local(self):
        """El script escribe en Qdrant: apuntarlo a la nube es igual de deliberado."""
        destinos = _destinos_no_locales(
            "postgresql://u:p@localhost:5432/db", "https://abc.cloud.qdrant.io:6333"
        )

        assert len(destinos) == 1
        assert "abc.cloud.qdrant.io" in destinos[0]

    def test_ambos_remotos_se_nombran_los_dos(self):
        destinos = _destinos_no_locales(
            "postgresql://u:p@db.abc.supabase.co:5432/postgres",
            "https://abc.cloud.qdrant.io:6333",
        )

        assert len(destinos) == 2


class TestExigirEmbeddingReal:
    def test_el_mock_aborta(self):
        """Con `MockEmbeddingService` se escribirían vectores de puros ceros en
        Qdrant, y eso no se arregla corrigiendo la configuración: hay que rehacerlos."""
        with pytest.raises(SystemExit):
            _exigir_embedding_real(MockEmbeddingService())

    def test_un_servicio_real_pasa(self):
        _exigir_embedding_real(FakeEmbeddingService())


class TestLotesPorLargo:
    def test_el_lote_por_defecto_es_chico(self):
        """Con 32 (el valor por defecto de sentence-transformers) BGE-M3 se cae por
        memoria con partidas largas."""
        assert TAMANO_LOTE_EMBEDDING == 8

    def test_los_lotes_no_superan_el_tamano(self):
        textos = [f"partida {i}" for i in range(20)]

        lotes = _lotes_por_largo(textos, 8)

        assert [len(lote) for lote in lotes] == [8, 8, 4]

    def test_agrupa_por_largo_para_no_rellenar_de_mas(self):
        """Textos de largo parecido juntos: el relleno de un lote lo pone el más largo."""
        largo = "x" * 400
        textos = [largo, "a", "bb", largo + "y", "ccc", "dddd"]

        lotes = _lotes_por_largo(textos, 3)

        assert lotes[0] == ["a", "bb", "ccc"]
        assert lotes[1] == ["dddd", largo, largo + "y"]

    def test_no_repite_textos_iguales(self):
        assert _lotes_por_largo(["a", "a", "b", "a"], 8) == [["a", "b"]]

    def test_sin_textos_no_hay_lotes(self):
        assert _lotes_por_largo([], 8) == []


class TestEmbeberPorLotes:
    async def test_devuelve_un_vector_por_texto_distinto(self):
        embedding = FakeEmbeddingPorTexto({"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0]})

        vectores = await _embeber_por_lotes(embedding, ["a", "b", "a"], 8)

        assert vectores == {"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0]}

    async def test_llama_al_modelo_lote_por_lote(self):
        embedding = FakeEmbeddingPorTexto()
        textos = [f"texto {i:02d}" for i in range(19)]

        await _embeber_por_lotes(embedding, textos, 8)

        assert [len(llamada) for llamada in embedding.calls] == [8, 8, 3]

    async def test_sin_textos_no_llama_al_modelo(self):
        embedding = FakeEmbeddingPorTexto()

        assert await _embeber_por_lotes(embedding, [], 8) == {}
        assert embedding.calls == []


class TestClasificar:
    def test_separa_lo_pendiente_de_lo_que_ya_esta(self):
        licitaciones = [
            (_id(1), ["a"]),
            (_id(2), ["b"]),
            (_id(3), ["c"]),
        ]
        resumen = Resumen()

        pendientes = _clasificar(licitaciones, {_id(2)}, resumen)

        assert [tender_id for tender_id, _ in pendientes] == [_id(1), _id(3)]
        assert resumen.revisadas == 3
        assert resumen.ya_indexadas == 1
        assert resumen.pendientes == 2
        assert resumen.textos == 2

    def test_las_que_no_tienen_partidas_no_se_indexan(self):
        """No hay nada que embeber; el scorer las cubre con su nombre y descripción."""
        resumen = Resumen()

        pendientes = _clasificar([(_id(1), []), (_id(2), ["a"])], set(), resumen)

        assert [tender_id for tender_id, _ in pendientes] == [_id(2)]
        assert resumen.sin_partidas == 1

    def test_una_indexada_sin_partidas_cuenta_como_sin_partidas(self):
        resumen = Resumen()

        _clasificar([(_id(1), [])], {_id(1)}, resumen)

        assert resumen.sin_partidas == 1
        assert resumen.ya_indexadas == 0


class TestRepartir:
    def test_arma_los_vectores_de_cada_licitacion_en_el_orden_de_sus_partidas(self):
        grupo = [(_id(1), ["a", "b"]), (_id(2), ["b", "c"])]
        vectores = {"a": [1.0], "b": [2.0], "c": [3.0]}

        assert _repartir(grupo, vectores) == [
            (_id(1), [[1.0], [2.0]]),
            (_id(2), [[2.0], [3.0]]),
        ]


class TestIndexarGrupo:
    async def test_guarda_un_upsert_por_licitacion(self):
        repo = InMemoryTenderItemVectorRepository()
        embedding = FakeEmbeddingPorTexto(
            {"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0], "c": [0.0, 0.0, 1.0]}
        )
        grupo = [(_id(1), ["a", "b"]), (_id(2), ["b", "c"])]

        indexadas = await _indexar_grupo(embedding, repo, grupo, tamano_lote=8)

        assert indexadas == 2
        assert repo.vectors == {
            _id(1): [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            _id(2): [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        }

    async def test_un_texto_compartido_se_embebe_una_sola_vez(self):
        embedding = FakeEmbeddingPorTexto()
        grupo = [(_id(1), ["a", "b"]), (_id(2), ["b", "c"])]

        await _indexar_grupo(embedding, InMemoryTenderItemVectorRepository(), grupo, 8)

        embebidos = [t for llamada in embedding.calls for t in llamada]
        assert sorted(embebidos) == ["a", "b", "c"]


class TestGruposPendientes:
    async def test_recorre_todas_las_paginas(self):
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 8)]
        resumen = Resumen()

        grupos = [
            grupo
            async for grupo in _grupos_pendientes(
                _fuente(licitaciones),
                InMemoryTenderItemVectorRepository(),
                tamano_grupo=3,
                limite=None,
                resumen=resumen,
            )
        ]

        assert [len(g) for g in grupos] == [3, 3, 1]
        assert resumen.revisadas == 7
        assert resumen.pendientes == 7

    async def test_omite_las_que_ya_tienen_vectores(self):
        repo = InMemoryTenderItemVectorRepository()
        await repo.upsert(_id(2), [[1.0]])
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 5)]
        resumen = Resumen()

        grupos = [
            grupo
            async for grupo in _grupos_pendientes(
                _fuente(licitaciones), repo, tamano_grupo=10, limite=None, resumen=resumen
            )
        ]

        assert [tender_id for tender_id, _ in grupos[0]] == [_id(1), _id(3), _id(4)]
        assert resumen.ya_indexadas == 1

    async def test_el_limite_corta_lo_que_se_indexa_en_la_corrida(self):
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 8)]

        grupos = [
            grupo
            async for grupo in _grupos_pendientes(
                _fuente(licitaciones),
                InMemoryTenderItemVectorRepository(),
                tamano_grupo=3,
                limite=4,
                resumen=Resumen(),
            )
        ]

        assert sum(len(g) for g in grupos) == 4

    async def test_una_pagina_de_puras_indexadas_no_corta_el_recorrido(self):
        """Reanudar pasa por páginas enteras ya hechas: no es señal de fin."""
        repo = InMemoryTenderItemVectorRepository()
        for n in range(1, 4):
            await repo.upsert(_id(n), [[1.0]])
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 6)]

        grupos = [
            grupo
            async for grupo in _grupos_pendientes(
                _fuente(licitaciones), repo, tamano_grupo=3, limite=None, resumen=Resumen()
            )
        ]

        assert [tender_id for g in grupos for tender_id, _ in g] == [_id(4), _id(5)]

    async def test_no_escribe_nada(self):
        """`--solo-contar` recorre lo mismo que la carga y no puede tocar Qdrant."""
        repo = InMemoryTenderItemVectorRepository()

        _ = [
            grupo
            async for grupo in _grupos_pendientes(
                _fuente([(_id(1), ["a"])]), repo, 10, None, Resumen()
            )
        ]

        assert repo.vectors == {}


class TestProcesar:
    async def test_indexa_todo_el_corpus(self):
        repo = InMemoryTenderItemVectorRepository()
        licitaciones = [(_id(n), [f"partida {n}", "comun"]) for n in range(1, 6)]

        resumen = await procesar(
            _fuente(licitaciones),
            FakeEmbeddingPorTexto(),
            repo,
            tamano_grupo=2,
            tamano_lote=8,
            limite=None,
        )

        assert set(repo.vectors) == {_id(n) for n in range(1, 6)}
        assert all(len(v) == 2 for v in repo.vectors.values())
        assert resumen.indexadas == 5

    async def test_es_reanudable_y_no_reembebe_lo_hecho(self):
        """Interrumpir y volver a correr solo paga lo que faltaba."""
        repo = InMemoryTenderItemVectorRepository()
        await repo.upsert(_id(1), [[9.0, 9.0, 9.0]])
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 4)]
        embedding = FakeEmbeddingPorTexto()

        await procesar(_fuente(licitaciones), embedding, repo, 10, 8, None)

        embebidos = [t for llamada in embedding.calls for t in llamada]
        assert sorted(embebidos) == ["partida 2", "partida 3"]
        # Y lo que ya estaba quedó intacto.
        assert repo.vectors[_id(1)] == [[9.0, 9.0, 9.0]]

    async def test_una_segunda_pasada_no_hace_nada(self):
        repo = InMemoryTenderItemVectorRepository()
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 4)]
        await procesar(_fuente(licitaciones), FakeEmbeddingPorTexto(), repo, 10, 8, None)
        embedding = FakeEmbeddingPorTexto()

        resumen = await procesar(_fuente(licitaciones), embedding, repo, 10, 8, None)

        assert embedding.calls == []
        assert resumen.indexadas == 0
        assert resumen.ya_indexadas == 3


class TestLectorSql:
    """La consulta que arma el lector, sin base de datos: se captura y se compila.

    No prueba que Postgres la ejecute (eso lo verifica quien corre el script con
    `--solo-contar`), pero sí que los filtros y la paginación estén donde deben.
    """

    @staticmethod
    async def _sql(monkeypatch, *, despues_de, incluir_cerradas) -> str:
        from sqlalchemy.dialects import postgresql

        from scripts import backfill_tender_item_vectors as script

        capturadas = []

        class Resultado:
            def all(self):
                return []

        class SesionFalsa:
            def __init__(self, _engine) -> None: ...

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_exc) -> None: ...

            async def exec(self, stmt):
                capturadas.append(stmt)
                return Resultado()

        monkeypatch.setattr(script, "AsyncSession", SesionFalsa)

        lector = script._lector_sql(object(), incluir_cerradas)  # type: ignore[arg-type]
        assert await lector(despues_de, 50) == []

        return str(
            capturadas[0].compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

    async def test_por_defecto_solo_las_abiertas(self, monkeypatch):
        sql = await self._sql(monkeypatch, despues_de=None, incluir_cerradas=False)

        assert "tender.status_id = 2" in sql
        assert "tender.closing_at >" in sql
        assert "ORDER BY tender.id" in sql
        assert "LIMIT 50" in sql

    async def test_con_incluir_cerradas_no_filtra_por_estado_ni_cierre(self, monkeypatch):
        sql = await self._sql(monkeypatch, despues_de=None, incluir_cerradas=True)

        assert "WHERE" not in sql

    async def test_pagina_por_id(self, monkeypatch):
        sql = await self._sql(monkeypatch, despues_de=_id(7), incluir_cerradas=True)

        assert f"tender.id > '{_id(7)}'" in sql

    async def test_la_primera_pagina_no_filtra_por_id(self, monkeypatch):
        sql = await self._sql(monkeypatch, despues_de=None, incluir_cerradas=True)

        assert "tender.id >" not in sql


# ---------------------------------------------------------------------------
# Payload: copiado desde el punto de "tenders"
# ---------------------------------------------------------------------------


def _payload(n: int, **extra) -> dict:
    """Un payload como el que guarda la ingesta, distinto por licitación."""
    return {
        "status_code": "publicada",
        "region_id": n,
        "provincia_id": None,
        "comuna_id": None,
        "available_amount_clp": 1000.0 * n,
        "closing_at": 1_782_000_000 + n,
        "published_at": 1_767_000_000 + n,
        **extra,
    }


def _payloads_de(por_licitacion: dict[uuid.UUID, dict]):
    """Un lector de payloads en memoria; registra qué ids se le pidieron."""
    pedidos: list[list[uuid.UUID]] = []

    async def leer(ids):
        pedidos.append(list(ids))
        return {i: dict(por_licitacion[i]) for i in ids if i in por_licitacion}

    leer.pedidos = pedidos  # type: ignore[attr-defined]
    return leer


def _punto(tender_id: uuid.UUID, payload: dict | None) -> MagicMock:
    punto = MagicMock()
    punto.id = str(tender_id)
    punto.payload = payload
    return punto


class TestLectorPayloads:
    """Lee el payload del punto de "tenders" con `retrieve`, en lotes."""

    async def test_consulta_la_coleccion_de_licitaciones_con_payload_y_sin_vectores(self):
        client = AsyncMock()
        tender_id = _id(1)
        client.retrieve.return_value = [_punto(tender_id, _payload(1))]

        leidos = await _lector_payloads(client)([tender_id])

        kwargs = client.retrieve.call_args.kwargs
        assert kwargs["collection_name"] == "tenders"
        assert kwargs["ids"] == [str(tender_id)]
        assert kwargs["with_payload"] is True
        assert kwargs["with_vectors"] is False
        assert leidos == {tender_id: _payload(1)}

    async def test_consulta_en_lotes(self):
        client = AsyncMock()
        ids = [_id(n) for n in range(1, 601)]

        async def retrieve(**kwargs):
            return [_punto(uuid.UUID(i), _payload(1)) for i in kwargs["ids"]]

        client.retrieve.side_effect = retrieve

        leidos = await _lector_payloads(client)(ids)

        tamanos = [len(c.kwargs["ids"]) for c in client.retrieve.call_args_list]
        assert tamanos == [256, 256, 88]
        assert set(leidos) == set(ids)

    async def test_copia_solo_los_campos_de_filtrado(self):
        """El payload de "tenders" es la fuente, pero a las partidas solo les
        interesan los campos por los que se filtra; el resto no debe viajar."""
        client = AsyncMock()
        client.retrieve.return_value = [_punto(_id(1), _payload(1, code="LIC-1", basura=True))]

        leidos = await _lector_payloads(client)([_id(1)])

        assert leidos == {_id(1): _payload(1)}

    async def test_omite_los_puntos_ausentes_y_los_que_no_tienen_payload(self):
        client = AsyncMock()
        client.retrieve.return_value = [_punto(_id(1), _payload(1)), _punto(_id(2), None)]

        leidos = await _lector_payloads(client)([_id(1), _id(2), _id(3)])

        assert set(leidos) == {_id(1)}

    async def test_sin_ids_no_consulta(self):
        client = AsyncMock()

        assert await _lector_payloads(client)([]) == {}
        client.retrieve.assert_not_called()


class TestIndexarGrupoConPayload:
    async def test_las_nuevas_se_suben_con_su_payload(self):
        repo = InMemoryTenderItemVectorRepository()
        grupo = [(_id(1), ["a"]), (_id(2), ["b"])]

        await _indexar_grupo(
            FakeEmbeddingPorTexto(), repo, grupo, 8, payloads={_id(1): _payload(1)}
        )

        assert repo.payloads == {_id(1): _payload(1), _id(2): {}}
        assert set(repo.vectors) == {_id(1), _id(2)}

    async def test_sin_payloads_se_sube_como_antes(self):
        repo = InMemoryTenderItemVectorRepository()

        await _indexar_grupo(FakeEmbeddingPorTexto(), repo, [(_id(1), ["a"])], 8)

        assert set(repo.vectors) == {_id(1)}
        assert repo.payloads == {_id(1): {}}


class TestProcesarConPayload:
    async def test_las_nuevas_reciben_el_payload_de_tenders(self):
        repo = InMemoryTenderItemVectorRepository()
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 4)]
        payloads = {_id(n): _payload(n) for n in range(1, 4)}

        resumen = await procesar(
            _fuente(licitaciones),
            FakeEmbeddingPorTexto(),
            repo,
            10,
            8,
            None,
            leer_payloads=_payloads_de(payloads),
        )

        assert repo.payloads == payloads
        assert resumen.indexadas == 3
        assert resumen.payloads_copiados == 0

    async def test_las_que_ya_tenian_vectores_reciben_el_payload_sin_reembeber(self):
        repo = InMemoryTenderItemVectorRepository()
        await repo.upsert(_id(1), [[9.0, 9.0, 9.0]])
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 3)]
        payloads = {_id(n): _payload(n) for n in range(1, 3)}
        embedding = FakeEmbeddingPorTexto()

        resumen = await procesar(
            _fuente(licitaciones),
            embedding,
            repo,
            10,
            8,
            None,
            leer_payloads=_payloads_de(payloads),
        )

        # Solo se embebió la que faltaba; la existente conserva sus vectores.
        assert [t for llamada in embedding.calls for t in llamada] == ["partida 2"]
        assert repo.vectors[_id(1)] == [[9.0, 9.0, 9.0]]
        assert repo.payloads == payloads
        assert resumen.indexadas == 1
        assert resumen.payloads_copiados == 1

    async def test_una_segunda_pasada_completa_los_payloads_de_todo_lo_indexado(self):
        """El caso real: la colección ya está cargada (sin payload) y se corre de nuevo."""
        repo = InMemoryTenderItemVectorRepository()
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 5)]
        await procesar(_fuente(licitaciones), FakeEmbeddingPorTexto(), repo, 10, 8, None)
        assert repo.payloads == {_id(n): {} for n in range(1, 5)}
        payloads = {_id(n): _payload(n) for n in range(1, 5)}
        embedding = FakeEmbeddingPorTexto()

        resumen = await procesar(
            _fuente(licitaciones),
            embedding,
            repo,
            3,
            8,
            None,
            leer_payloads=_payloads_de(payloads),
        )

        assert embedding.calls == []
        assert repo.payloads == payloads
        assert resumen.payloads_copiados == 4
        assert resumen.indexadas == 0

    async def test_si_tenders_no_tiene_payload_se_indexa_igual_y_se_cuenta(self):
        repo = InMemoryTenderItemVectorRepository()
        await repo.upsert(_id(1), [[1.0, 0.0, 0.0]])
        licitaciones = [(_id(1), ["a"]), (_id(2), ["b"])]

        resumen = await procesar(
            _fuente(licitaciones),
            FakeEmbeddingPorTexto(),
            repo,
            10,
            8,
            None,
            leer_payloads=_payloads_de({}),
        )

        assert set(repo.vectors) == {_id(1), _id(2)}
        assert repo.payloads[_id(1)] == {}
        assert resumen.indexadas == 1
        assert resumen.payloads_copiados == 0
        assert resumen.sin_payload == 2

    async def test_lee_los_payloads_en_lotes_por_pagina(self):
        repo = InMemoryTenderItemVectorRepository()
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 8)]
        leer = _payloads_de({_id(n): _payload(n) for n in range(1, 8)})

        await procesar(
            _fuente(licitaciones),
            FakeEmbeddingPorTexto(),
            repo,
            3,
            8,
            None,
            leer_payloads=leer,
        )

        assert len(leer.pedidos) == 3  # un grupo por página, no una lectura por licitación
        assert [len(p) for p in leer.pedidos] == [3, 3, 1]


class TestSoloPayload:
    async def test_copia_los_payloads_sin_cargar_el_modelo(self):
        """`--solo-payload` no recibe servicio de embeddings: no lo necesita."""
        repo = InMemoryTenderItemVectorRepository()
        await repo.upsert(_id(1), [[1.0, 0.0, 0.0]])
        await repo.upsert(_id(2), [[0.0, 1.0, 0.0]])
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 3)]
        payloads = {_id(n): _payload(n) for n in range(1, 3)}

        resumen = await procesar(
            _fuente(licitaciones),
            None,
            repo,
            10,
            8,
            None,
            leer_payloads=_payloads_de(payloads),
            solo_payload=True,
        )

        assert repo.payloads == payloads
        assert repo.vectors == {_id(1): [[1.0, 0.0, 0.0]], _id(2): [[0.0, 1.0, 0.0]]}
        assert resumen.payloads_copiados == 2
        assert resumen.indexadas == 0

    async def test_no_indexa_las_que_faltan_pero_las_cuenta_como_pendientes(self):
        repo = InMemoryTenderItemVectorRepository()
        await repo.upsert(_id(1), [[1.0, 0.0, 0.0]])
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 4)]
        payloads = {_id(n): _payload(n) for n in range(1, 4)}

        resumen = await procesar(
            _fuente(licitaciones),
            None,
            repo,
            10,
            8,
            None,
            leer_payloads=_payloads_de(payloads),
            solo_payload=True,
        )

        assert set(repo.vectors) == {_id(1)}
        assert set(repo.payloads) == {_id(1)}
        assert resumen.pendientes == 2
        assert resumen.indexadas == 0
        assert resumen.payloads_copiados == 1

    async def test_recorre_todas_las_paginas(self):
        repo = InMemoryTenderItemVectorRepository()
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 8)]
        for tender_id, _ in licitaciones:
            await repo.upsert(tender_id, [[1.0, 0.0, 0.0]])
        payloads = {_id(n): _payload(n) for n in range(1, 8)}

        resumen = await procesar(
            _fuente(licitaciones),
            None,
            repo,
            3,
            8,
            None,
            leer_payloads=_payloads_de(payloads),
            solo_payload=True,
        )

        assert repo.payloads == payloads
        assert resumen.payloads_copiados == 7

    async def test_informa_el_avance_pagina_a_pagina(self):
        """No hay grupos que indexar, así que el avance sale de los payloads."""
        repo = InMemoryTenderItemVectorRepository()
        licitaciones = [(_id(n), [f"partida {n}"]) for n in range(1, 8)]
        for tender_id, _ in licitaciones:
            await repo.upsert(tender_id, [[1.0, 0.0, 0.0]])
        copiados_por_aviso: list[int] = []

        await procesar(
            _fuente(licitaciones),
            None,
            repo,
            3,
            8,
            None,
            leer_payloads=_payloads_de({_id(n): _payload(n) for n in range(1, 8)}),
            solo_payload=True,
            en_progreso=lambda resumen: copiados_por_aviso.append(resumen.payloads_copiados),
        )

        assert copiados_por_aviso == [3, 6, 7]

    async def test_sin_modelo_ni_solo_payload_es_un_error_de_uso(self):
        with pytest.raises(ValueError, match="embedding"):
            await procesar(_fuente([]), None, InMemoryTenderItemVectorRepository(), 10, 8, None)

    async def test_solo_payload_sin_lector_es_un_error_de_uso(self):
        with pytest.raises(ValueError, match="leer_payloads"):
            await procesar(
                _fuente([]),
                None,
                InMemoryTenderItemVectorRepository(),
                10,
                8,
                None,
                solo_payload=True,
            )


class TestCargarSoloPayload:
    """El cableado de `cargar`: con `--solo-payload` no se toca el modelo."""

    async def test_no_construye_el_servicio_de_embeddings(self, monkeypatch):
        from app import bootstrap
        from scripts import backfill_tender_item_vectors as script

        def no_debe_llamarse():
            raise AssertionError("--solo-payload no debe cargar el modelo de embeddings")

        monkeypatch.setattr(bootstrap, "build_embedding_service", no_debe_llamarse)

        repo = InMemoryTenderItemVectorRepository()
        await repo.upsert(_id(1), [[1.0, 0.0, 0.0]])
        qdrant = AsyncMock()
        qdrant.retrieve.return_value = [_punto(_id(1), _payload(1))]
        engine = SimpleNamespace(dispose=AsyncMock())
        asegurada = []

        async def ensure_collection() -> None:
            asegurada.append(True)

        repo.ensure_collection = ensure_collection  # type: ignore[attr-defined]
        monkeypatch.setattr(script, "_conectar", lambda: (engine, qdrant))
        monkeypatch.setattr(script, "QdrantTenderItemVectorRepository", lambda **_kw: repo)
        monkeypatch.setattr(
            script, "_lector_sql", lambda _engine, _cerradas: _fuente([(_id(1), ["a"])])
        )

        await script.cargar(
            argparse.Namespace(
                solo_payload=True, incluir_cerradas=False, limite=None, tamano_lote=8
            )
        )

        assert repo.payloads == {_id(1): _payload(1)}
        assert asegurada == [True]  # los índices de payload existen antes de escribir
        qdrant.close.assert_awaited_once()


class TestMainSoloPayload:
    """Las guardas de `main` valen también para el modo nuevo."""

    @staticmethod
    def _ajustes(monkeypatch, *, database_url: str, qdrant_url: str) -> None:
        from scripts import backfill_tender_item_vectors as script

        monkeypatch.setattr(
            script,
            "settings",
            SimpleNamespace(
                database_url=database_url,
                qdrant_url=qdrant_url,
                qdrant_api_key=None,
                embedding_provider="mock",
                embedding_vector_size=4,
            ),
        )

    def test_contra_un_destino_remoto_exige_confirmar_produccion(self, monkeypatch):
        from scripts import backfill_tender_item_vectors as script

        self._ajustes(
            monkeypatch,
            database_url="postgresql://u:p@db.abc.supabase.co:5432/postgres",
            qdrant_url="http://localhost:6333",
        )
        monkeypatch.setattr(sys, "argv", ["prog", "--solo-payload"])

        with pytest.raises(SystemExit) as salida:
            script.main()

        assert "--confirmar-produccion" in str(salida.value)

    def test_no_se_combina_con_solo_contar(self, monkeypatch):
        from scripts import backfill_tender_item_vectors as script

        self._ajustes(
            monkeypatch,
            database_url="postgresql://u:p@localhost:5432/db",
            qdrant_url="http://localhost:6333",
        )
        monkeypatch.setattr(sys, "argv", ["prog", "--solo-payload", "--solo-contar"])

        with pytest.raises(SystemExit) as salida:
            script.main()

        assert "--solo-contar" in str(salida.value)

    def test_no_se_combina_con_limite(self, monkeypatch):
        """`--limite` acota lo que se indexa; con `--solo-payload` no se indexa nada,
        y ignorarlo en silencio haría creer que la corrida de prueba fue acotada."""
        from scripts import backfill_tender_item_vectors as script

        self._ajustes(
            monkeypatch,
            database_url="postgresql://u:p@localhost:5432/db",
            qdrant_url="http://localhost:6333",
        )
        monkeypatch.setattr(sys, "argv", ["prog", "--solo-payload", "--limite", "5"])

        with pytest.raises(SystemExit) as salida:
            script.main()

        assert "--limite" in str(salida.value)
