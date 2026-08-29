"""La metadata se inserta por lotes, no comprobando existencia una por una.

El bucle hacía un `SELECT ... WHERE code = :code` por cada licitación del
listado. Con la ventana de 24 h da igual, pero una carga inicial trae miles, y
desde Chile contra Supabase en US East cada viaje son **133 ms medidos**: 2.000
licitaciones son 4,4 minutos de pura espera que no calculan nada.

`tender_metadata.code` ya tiene índice único, así que el duplicado lo puede
resolver Postgres con ON CONFLICT sin consultar antes.
"""

from app.infrastructure.services.tenders.tender_ingestion_service import (
    LOTE_METADATA,
    _lotes,
)


class TestTroceadoEnLotes:
    def test_una_lista_corta_va_en_un_solo_lote(self):
        assert list(_lotes(["a", "b", "c"], 10)) == [["a", "b", "c"]]

    def test_se_trocea_al_llegar_al_tamano(self):
        assert list(_lotes([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]

    def test_una_lista_vacia_no_produce_lotes(self):
        assert list(_lotes([], 10)) == []

    def test_el_tamano_por_defecto_deja_margen_al_limite_de_postgres(self):
        """Postgres topa en 65.535 parámetros por sentencia.

        Cada fila lleva 5 columnas, así que el techo real son ~13.000 filas.
        El lote por defecto tiene que quedar cómodamente por debajo.
        """
        assert LOTE_METADATA * 5 < 65535
