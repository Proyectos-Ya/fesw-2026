"""Conteo por colección de la purga única de Qdrant (plan 306).

En `tender_items` y `tender_lexical` el payload de una cerrada sigue diciendo
`publicada`, así que contar por payload no dice cuánto sobra. Se cuenta cuántas
de las licitaciones inactivas según Postgres tienen todavía un punto.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from scripts.purgar_vectores_inactivos import COLECCIONES, contar_existentes

pytestmark = pytest.mark.asyncio


def _punto(pid) -> MagicMock:
    punto = MagicMock()
    punto.id = str(pid)
    return punto


def _con_colecciones(*nombres: str) -> AsyncMock:
    client = AsyncMock()
    respuesta = MagicMock()
    respuesta.collections = []
    for nombre in nombres:
        coleccion = MagicMock()
        coleccion.name = nombre
        respuesta.collections.append(coleccion)
    client.get_collections.return_value = respuesta
    return client


def test_cuenta_las_tres_colecciones():
    assert COLECCIONES == ("tenders", "tender_items", "tender_lexical")


async def test_cuenta_solo_los_ids_que_tienen_punto():
    ids = [uuid4() for _ in range(3)]
    client = _con_colecciones("tender_items")
    client.retrieve.return_value = [_punto(ids[0]), _punto(ids[2])]

    assert await contar_existentes(client, "tender_items", ids) == 2
    kwargs = client.retrieve.call_args.kwargs
    assert kwargs["with_payload"] is False and kwargs["with_vectors"] is False


async def test_pide_en_lotes():
    ids = [uuid4() for _ in range(1_200)]
    client = _con_colecciones("tenders")
    client.retrieve.return_value = []

    await contar_existentes(client, "tenders", ids)

    assert [len(c.kwargs["ids"]) for c in client.retrieve.call_args_list] == [
        500,
        500,
        200,
    ]


async def test_una_coleccion_que_no_existe_no_tiene_puntos():
    """En local puede faltar `tender_lexical`: no es un error de la purga."""
    client = _con_colecciones("tenders")

    assert await contar_existentes(client, "tender_lexical", [uuid4()]) is None
    client.retrieve.assert_not_called()
