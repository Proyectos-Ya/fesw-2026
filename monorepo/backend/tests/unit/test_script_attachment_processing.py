"""Pruebas del script manual de procesamiento de anexos (plan 233, decisión 4)."""

import argparse

import pytest

from scripts.attachment_processing import main_async, parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.max_trabajos == 1
    assert args.solo_barrido is False
    assert args.reintentar_fallidos is False
    assert args.confirmar_produccion is False


def test_parse_args_custom():
    args = parse_args([
        "--max-trabajos", "5",
        "--solo-barrido",
        "--reintentar-fallidos",
        "--confirmar-produccion",
    ])
    assert args.max_trabajos == 5
    assert args.solo_barrido is True
    assert args.reintentar_fallidos is True
    assert args.confirmar_produccion is True


@pytest.mark.asyncio
async def test_se_niega_contra_supabase_sin_confirmar(monkeypatch):
    args = argparse.Namespace(
        confirmar_produccion=False,
        max_trabajos=1,
        solo_barrido=False,
        reintentar_fallidos=False,
    )
    from app.config import settings

    monkeypatch.setattr(
        type(settings),
        "database_url",
        property(
            lambda self: "postgresql+asyncpg://postgres:pass@db.xyz.supabase.co:5432/postgres"
        ),
    )
    codigo = await main_async(args)
    assert codigo == 2
