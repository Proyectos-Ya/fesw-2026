from datetime import datetime, timedelta
from uuid import uuid4

from app.domain.entities.tender_share_link import (
    SHARE_LINK_TTL,
    ShareLinkStatus,
    TenderShareLink,
    hash_share_token,
)

AHORA = datetime(2026, 9, 28, 12, 0, 0)


def _emitir(now: datetime = AHORA) -> tuple[TenderShareLink, str]:
    return TenderShareLink.emitir(
        tender_id=uuid4(), supplier_id=uuid4(), created_by=uuid4(), now=now
    )


class TestEmision:
    def test_vence_a_los_siete_dias_exactos(self):
        # Criterio 1: la URL tiene vigencia de 7 días.
        enlace, _ = _emitir()

        assert SHARE_LINK_TTL == timedelta(days=7)
        assert enlace.expires_at == AHORA + timedelta(days=7)

    def test_guarda_solo_el_hash_del_token(self):
        # Quien lea la base no puede armar la URL: el token no se guarda.
        enlace, token = _emitir()

        assert enlace.token_hash == hash_share_token(token)
        assert token not in enlace.model_dump_json()

    def test_cada_emision_da_un_token_distinto(self):
        _, uno = _emitir()
        _, otro = _emitir()

        assert uno != otro

    def test_el_token_es_largo_y_apto_para_una_url(self):
        _, token = _emitir()

        # 32 bytes en base64 url-safe: ~43 caracteres, sin '/' ni '+'.
        assert len(token) >= 43
        assert "/" not in token and "+" not in token


class TestEstado:
    def test_recien_emitido_esta_activo(self):
        enlace, _ = _emitir()

        assert enlace.estado(AHORA) is ShareLinkStatus.ACTIVO

    def test_un_segundo_antes_de_vencer_sigue_activo(self):
        enlace, _ = _emitir()

        momento = AHORA + timedelta(days=7) - timedelta(seconds=1)
        assert enlace.estado(momento) is ShareLinkStatus.ACTIVO

    def test_al_cumplir_siete_dias_caduca(self):
        # Criterio 6: cumplidos los 7 días, se deniega el acceso.
        enlace, _ = _emitir()

        assert enlace.estado(AHORA + timedelta(days=7)) is ShareLinkStatus.CADUCADO

    def test_revocado_deja_de_servir_al_instante(self):
        # Criterio 7: "Revocar" invalida la URL instantáneamente.
        enlace, _ = _emitir()

        revocado = enlace.revocar(AHORA)

        assert revocado.estado(AHORA) is ShareLinkStatus.REVOCADO
        assert revocado.revoked_at == AHORA

    def test_revocado_se_informa_como_revocado_aunque_tambien_haya_vencido(self):
        # El motivo más preciso es que alguien lo cortó, no que pasó el tiempo.
        enlace, _ = _emitir()

        revocado = enlace.revocar(AHORA + timedelta(days=1))

        assert revocado.estado(AHORA + timedelta(days=30)) is ShareLinkStatus.REVOCADO

    def test_revocar_dos_veces_conserva_la_primera_fecha(self):
        enlace, _ = _emitir()

        revocado = enlace.revocar(AHORA).revocar(AHORA + timedelta(hours=2))

        assert revocado.revoked_at == AHORA

    def test_revocar_no_modifica_el_original(self):
        enlace, _ = _emitir()

        enlace.revocar(AHORA)

        assert enlace.revoked_at is None


class TestHash:
    def test_es_sha256_en_hexadecimal(self):
        assert hash_share_token("abc") == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )
