"""Settings del almacenamiento de anexos y la subida manual (plan 233, decisión 2).

Todas son opcionales: sin R2 la API arranca igual (la subida queda apagada, o en
disco local con `IS_DEV`). Lo que sí se exige es que R2, si se configura, esté
completo: una cuenta sin clave dejaría arrancar un despliegue que falla en la
primera subida.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {
    "postgres_password": "x",
    "gemini_api_key": "x",
    "gemini_model": "x",
    "mercado_publico_api_key": "x",
    "supabase_url": "http://127.0.0.1:54321",
}

R2_COMPLETO = {
    "r2_account_id": "cuenta",
    "r2_access_key_id": "clave",
    "r2_secret_access_key": "secreto",
    "r2_bucket": "chiripa-anexos",
}


def _construir(**extra) -> Settings:
    return Settings(_env_file=None, **BASE, **extra)  # type: ignore[arg-type,call-arg]


def test_por_defecto_no_hay_r2_y_el_tope_es_cien() -> None:
    s = _construir()

    assert s.r2_enabled is False
    assert s.attachment_manual_uploads_per_month == 100
    assert s.attachment_local_storage_dir == "storage/attachments"
    assert s.attachment_local_storage_public_url == "http://localhost:8000"


def test_con_las_cuatro_variables_r2_queda_habilitado() -> None:
    assert _construir(**R2_COMPLETO).r2_enabled is True


def test_r2_incompleto_no_arranca_y_dice_que_falta() -> None:
    with pytest.raises(ValidationError) as info:
        _construir(r2_account_id="x")

    assert "R2_ACCESS_KEY_ID" in str(info.value)


def test_una_variable_r2_vacia_es_ausente() -> None:
    s = _construir(r2_account_id="  ")

    assert s.r2_account_id is None
    assert s.r2_enabled is False


def test_el_tope_mensual_tiene_que_ser_positivo() -> None:
    with pytest.raises(ValidationError):
        _construir(attachment_manual_uploads_per_month=0)


def test_se_leen_de_las_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATTACHMENT_MANUAL_UPLOADS_PER_MONTH", "7")
    monkeypatch.setenv("ATTACHMENT_LOCAL_STORAGE_DIR", "otro/lugar")
    for nombre, valor in R2_COMPLETO.items():
        monkeypatch.setenv(nombre.upper(), valor)

    s = _construir()

    assert s.attachment_manual_uploads_per_month == 7
    assert s.attachment_local_storage_dir == "otro/lugar"
    assert s.r2_bucket == "chiripa-anexos"
    assert s.r2_enabled is True


def test_la_url_publica_pierde_la_barra_final() -> None:
    s = _construir(attachment_local_storage_public_url="http://localhost:8000/")

    assert s.attachment_local_storage_public_url == "http://localhost:8000"
