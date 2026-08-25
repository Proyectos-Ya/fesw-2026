"""El dataset del xlsx envejece: al cargarlo hay que revivir las licitaciones."""

import pandas as pd

from tests.matching_evaluation.date_shift import desplazar_licitaciones_vencidas

AHORA = pd.Timestamp("2026-08-24 12:00:00")


def _licitacion(publicada: str, cierre: str, cambio: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "published_at": [pd.Timestamp(publicada)],
            "closing_at": [pd.Timestamp(cierre)],
            "last_change_at": [pd.Timestamp(cambio)],
        }
    )


def test_licitacion_vencida_se_corre_un_mes():
    df = _licitacion("2026-08-17 15:34", "2026-08-18 15:38", "2026-08-18 01:12")

    resultado = desplazar_licitaciones_vencidas(df, ahora=AHORA)

    assert resultado.loc[0, "closing_at"] == pd.Timestamp("2026-09-18 15:38")
    # Las tres fechas se mueven juntas: si solo se corriera el cierre, la
    # licitación quedaría publicada un mes antes de lo que dice el resto.
    assert resultado.loc[0, "published_at"] == pd.Timestamp("2026-09-17 15:34")
    assert resultado.loc[0, "last_change_at"] == pd.Timestamp("2026-09-18 01:12")


def test_licitacion_vigente_no_se_toca():
    df = _licitacion("2026-08-17 15:34", "2026-08-31 10:00", "2026-08-18 01:12")

    resultado = desplazar_licitaciones_vencidas(df, ahora=AHORA)

    assert resultado.loc[0, "closing_at"] == pd.Timestamp("2026-08-31 10:00")
    assert resultado.loc[0, "published_at"] == pd.Timestamp("2026-08-17 15:34")


def test_se_suman_los_meses_necesarios():
    """Un dataset viejo necesita más de un mes para volver a estar vigente."""
    df = _licitacion("2026-05-17 15:34", "2026-05-18 15:38", "2026-05-18 01:12")

    resultado = desplazar_licitaciones_vencidas(df, ahora=AHORA)

    assert resultado.loc[0, "closing_at"] == pd.Timestamp("2026-09-18 15:38")


def test_no_muta_el_dataframe_original():
    df = _licitacion("2026-08-17 15:34", "2026-08-18 15:38", "2026-08-18 01:12")

    desplazar_licitaciones_vencidas(df, ahora=AHORA)

    assert df.loc[0, "closing_at"] == pd.Timestamp("2026-08-18 15:38")


def test_fechas_nulas_no_rompen_el_desplazamiento():
    df = _licitacion("2026-08-17 15:34", "2026-08-18 15:38", "2026-08-18 01:12")
    df.loc[0, "last_change_at"] = pd.NaT

    resultado = desplazar_licitaciones_vencidas(df, ahora=AHORA)

    assert resultado.loc[0, "closing_at"] == pd.Timestamp("2026-09-18 15:38")
    assert pd.isna(resultado.loc[0, "last_change_at"])
