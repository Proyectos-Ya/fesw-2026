from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.entities.licitacion import ItemLicitacion, Licitacion
from app.domain.errors.licitacion_errors import LicitacionNoEncontrada, LicitacionYaExiste

FECHA_CIERRE = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)

DATOS_MINIMOS: dict = {
    "codigo_externo": "1234-5-LQ24",
    "nombre": "Adquisición de equipos computacionales",
    "organismo_nombre": "Ministerio de Educación",
    "fecha_cierre": FECHA_CIERRE,
    "region": "Metropolitana",
    "estado": "activa",
}


class TestItemLicitacion:
    def test_creacion_con_campos_obligatorios(self) -> None:
        item = ItemLicitacion(nombre="Notebook", descripcion="Intel i7 16GB RAM")
        assert item.nombre == "Notebook"
        assert item.descripcion == "Intel i7 16GB RAM"

    def test_descripcion_es_opcional(self) -> None:
        item = ItemLicitacion(nombre="Monitor")
        assert item.descripcion is None

    def test_es_inmutable(self) -> None:
        item = ItemLicitacion(nombre="Teclado")
        with pytest.raises(Exception):
            item.nombre = "Mouse"  # type: ignore[misc]


class TestLicitacion:
    def test_creacion_con_campos_obligatorios(self) -> None:
        licitacion = Licitacion(**DATOS_MINIMOS)
        assert licitacion.codigo_externo == "1234-5-LQ24"
        assert licitacion.nombre == "Adquisición de equipos computacionales"
        assert licitacion.organismo_nombre == "Ministerio de Educación"
        assert licitacion.fecha_cierre == FECHA_CIERRE
        assert licitacion.region == "Metropolitana"
        assert licitacion.estado == "activa"

    def test_id_es_uuid_generado_automaticamente(self) -> None:
        licitacion = Licitacion(**DATOS_MINIMOS)
        assert isinstance(licitacion.id, UUID)

    def test_dos_instancias_tienen_ids_distintos(self) -> None:
        a = Licitacion(**DATOS_MINIMOS)
        b = Licitacion(**DATOS_MINIMOS)
        assert a.id != b.id

    def test_fecha_ingesta_se_asigna_automaticamente(self) -> None:
        antes = datetime.now(timezone.utc)
        licitacion = Licitacion(**DATOS_MINIMOS)
        despues = datetime.now(timezone.utc)
        assert antes <= licitacion.fecha_ingesta <= despues

    def test_campos_opcionales_son_none_por_defecto(self) -> None:
        licitacion = Licitacion(**DATOS_MINIMOS)
        assert licitacion.descripcion is None
        assert licitacion.monto_estimado is None
        assert licitacion.qdrant_vector_id is None
        assert licitacion.version_modelo is None

    def test_listas_opcionales_son_vacias_por_defecto(self) -> None:
        licitacion = Licitacion(**DATOS_MINIMOS)
        assert licitacion.categorias == []
        assert licitacion.items == []

    def test_creacion_con_todos_los_campos(self) -> None:
        item = ItemLicitacion(nombre="Notebook", descripcion="Intel i7")
        licitacion = Licitacion(
            **DATOS_MINIMOS,
            descripcion="Equipos para colegios",
            monto_estimado=50_000_000.0,
            categorias=["Tecnología", "Computación"],
            items=[item],
        )
        assert licitacion.descripcion == "Equipos para colegios"
        assert licitacion.monto_estimado == 50_000_000.0
        assert licitacion.categorias == ["Tecnología", "Computación"]
        assert len(licitacion.items) == 1
        assert licitacion.items[0].nombre == "Notebook"

    def test_es_inmutable(self) -> None:
        licitacion = Licitacion(**DATOS_MINIMOS)
        with pytest.raises(Exception):
            licitacion.nombre = "Otro nombre"  # type: ignore[misc]

    def test_qdrant_vector_id_puede_ser_uuid(self) -> None:
        from uuid import uuid4
        vector_id = uuid4()
        licitacion = Licitacion(**DATOS_MINIMOS, qdrant_vector_id=vector_id)
        assert licitacion.qdrant_vector_id == vector_id

    def test_version_modelo_puede_asignarse(self) -> None:
        licitacion = Licitacion(**DATOS_MINIMOS, version_modelo="bge-m3-v1")
        assert licitacion.version_modelo == "bge-m3-v1"


class TestLicitacionErrors:
    def test_licitacion_no_encontrada_contiene_identificador(self) -> None:
        error = LicitacionNoEncontrada("1234-5-LQ24")
        assert "1234-5-LQ24" in str(error)
        assert error.identifier == "1234-5-LQ24"

    def test_licitacion_ya_existe_contiene_codigo_externo(self) -> None:
        error = LicitacionYaExiste("1234-5-LQ24")
        assert "1234-5-LQ24" in str(error)
        assert error.codigo_externo == "1234-5-LQ24"

    def test_licitacion_no_encontrada_es_exception(self) -> None:
        assert issubclass(LicitacionNoEncontrada, Exception)

    def test_licitacion_ya_existe_es_exception(self) -> None:
        assert issubclass(LicitacionYaExiste, Exception)
