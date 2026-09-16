"""La conexión que arman los scripts de ingesta.

En Railway la base se alcanza por el pooler de Supabase en modo transacción, que
no soporta sentencias preparadas. La API lo resuelve en `app/infrastructure/db.py`
con `DB_DISABLE_PREPARED_STATEMENTS`; el cron armaba su propio engine sin esos
ajustes y fallaba de forma intermitente con `prepared statement ... does not
exist` (primera corrida en `dev test`, 16-sep-2026). En local no se ve porque
ahí la conexión es directa.
"""

import app.bootstrap
import app.infrastructure.db as db
from app.config import settings
from scripts.ingesta_compartida import construir_servicio


def _capturar_engine(monkeypatch) -> list[dict]:
    llamadas: list[dict] = []
    original = db.create_async_engine

    def espia(url, **kwargs):
        llamadas.append(kwargs)
        return original(url, **kwargs)

    monkeypatch.setattr(db, "create_async_engine", espia)
    monkeypatch.setattr(app.bootstrap, "build_embedding_service", lambda: object())
    return llamadas


def test_detras_del_pooler_el_cron_no_usa_sentencias_preparadas(monkeypatch):
    monkeypatch.setattr(settings, "db_disable_prepared_statements", True)
    llamadas = _capturar_engine(monkeypatch)

    construir_servicio()

    assert len(llamadas) == 1
    assert llamadas[0]["connect_args"] == {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }


def test_con_conexion_directa_se_dejan_las_de_asyncpg(monkeypatch):
    monkeypatch.setattr(settings, "db_disable_prepared_statements", False)
    llamadas = _capturar_engine(monkeypatch)

    construir_servicio()

    assert llamadas[0]["connect_args"] == {}
