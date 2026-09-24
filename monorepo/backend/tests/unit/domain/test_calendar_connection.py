from datetime import datetime, time, timedelta
from uuid import uuid4

from app.domain.entities.calendar import (
    CalendarConnection,
    CalendarOAuthState,
    CalendarProvider,
)

AHORA = datetime(2026, 10, 1, 12, 0)


def _conexion(expira_en: timedelta) -> CalendarConnection:
    return CalendarConnection(
        user_id=uuid4(),
        provider=CalendarProvider.GOOGLE,
        access_token="token-de-acceso",
        refresh_token="token-de-refresco",
        expires_at=AHORA + expira_en,
        account_email="usuario@gmail.com",
    )


class TestConexion:
    def test_un_token_vigente_no_necesita_refresco(self):
        assert _conexion(timedelta(minutes=30)).needs_refresh(AHORA) is False

    def test_un_token_vencido_necesita_refresco(self):
        assert _conexion(timedelta(minutes=-1)).needs_refresh(AHORA) is True

    def test_se_refresca_con_un_minuto_de_margen(self):
        # Evita mandar a Google un token que expira durante la petición.
        assert _conexion(timedelta(seconds=30)).needs_refresh(AHORA) is True

    def test_los_tokens_no_aparecen_al_imprimir_ni_serializar(self):
        conexion = _conexion(timedelta(hours=1))

        assert "token-de-acceso" not in repr(conexion)
        assert "token-de-refresco" not in repr(conexion)
        assert "token-de-acceso" not in conexion.model_dump_json()

    def test_los_tokens_se_leen_explicitamente(self):
        conexion = _conexion(timedelta(hours=1))

        assert conexion.access_token.get_secret_value() == "token-de-acceso"


class TestEstadoOAuth:
    def _estado(self, user_id=None, expira_en=timedelta(minutes=10)) -> CalendarOAuthState:
        return CalendarOAuthState(
            state_hash="a" * 64,
            user_id=user_id or uuid4(),
            provider=CalendarProvider.GOOGLE,
            tender_id=uuid4(),
            milestone_ids=[uuid4()],
            default_time=time(9, 0),
            expires_at=AHORA + expira_en,
        )

    def test_es_valido_para_el_mismo_usuario_antes_de_vencer(self):
        user_id = uuid4()

        assert self._estado(user_id).is_valid_for(user_id, AHORA) is True

    def test_no_es_valido_para_otro_usuario(self):
        assert self._estado().is_valid_for(uuid4(), AHORA) is False

    def test_no_es_valido_despues_de_vencer(self):
        user_id = uuid4()
        estado = self._estado(user_id, expira_en=timedelta(seconds=-1))

        assert estado.is_valid_for(user_id, AHORA) is False
