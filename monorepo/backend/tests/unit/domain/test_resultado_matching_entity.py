from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.domain.entities.resultado_matching import ResultadoMatching


class TestResultadoMatching:
    def test_creacion_con_campos_obligatorios(self) -> None:
        proveedor_id = uuid4()
        licitacion_id = uuid4()
        resultado = ResultadoMatching(
            proveedor_id=proveedor_id,
            licitacion_id=licitacion_id,
            score_similitud=0.87,
            score_final=0.87,
            version_modelo="bge-m3-v1",
        )
        assert resultado.proveedor_id == proveedor_id
        assert resultado.licitacion_id == licitacion_id
        assert resultado.score_similitud == 0.87
        assert resultado.score_final == 0.87
        assert resultado.version_modelo == "bge-m3-v1"

    def test_id_generado_automaticamente(self) -> None:
        resultado = ResultadoMatching(
            proveedor_id=uuid4(),
            licitacion_id=uuid4(),
            score_similitud=0.5,
            score_final=0.5,
            version_modelo="bge-m3-v1",
        )
        assert isinstance(resultado.id, UUID)

    def test_dos_instancias_tienen_ids_distintos(self) -> None:
        kwargs = {
            "proveedor_id": uuid4(),
            "licitacion_id": uuid4(),
            "score_similitud": 0.5,
            "score_final": 0.5,
            "version_modelo": "bge-m3-v1",
        }
        assert ResultadoMatching(**kwargs).id != ResultadoMatching(**kwargs).id

    def test_fecha_calculo_asignada_automaticamente(self) -> None:
        antes = datetime.now(timezone.utc)
        resultado = ResultadoMatching(
            proveedor_id=uuid4(),
            licitacion_id=uuid4(),
            score_similitud=0.9,
            score_final=0.9,
            version_modelo="bge-m3-v1",
        )
        despues = datetime.now(timezone.utc)
        assert antes <= resultado.fecha_calculo <= despues

    def test_score_reranker_es_none_por_defecto(self) -> None:
        resultado = ResultadoMatching(
            proveedor_id=uuid4(),
            licitacion_id=uuid4(),
            score_similitud=0.75,
            score_final=0.75,
            version_modelo="bge-m3-v1",
        )
        assert resultado.score_reranker is None

    def test_score_reranker_puede_asignarse(self) -> None:
        resultado = ResultadoMatching(
            proveedor_id=uuid4(),
            licitacion_id=uuid4(),
            score_similitud=0.75,
            score_reranker=0.82,
            score_final=0.82,
            version_modelo="bge-m3-v1",
        )
        assert resultado.score_reranker == 0.82

    def test_es_inmutable(self) -> None:
        resultado = ResultadoMatching(
            proveedor_id=uuid4(),
            licitacion_id=uuid4(),
            score_similitud=0.6,
            score_final=0.6,
            version_modelo="bge-m3-v1",
        )
        with pytest.raises(Exception):
            resultado.score_final = 0.9  # type: ignore[misc]
