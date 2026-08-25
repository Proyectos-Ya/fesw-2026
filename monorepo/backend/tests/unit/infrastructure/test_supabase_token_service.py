"""Verificación de los tokens que emite Supabase Auth.

Este es el único punto donde el backend decide en quién cree. Todo lo que
aceptemos de más acá se convierte en una sesión válida de cualquier usuario, así
que los casos negativos importan más que el positivo.
"""

from datetime import timedelta

import pytest

from app.domain.errors.auth_errors import InvalidToken
from app.infrastructure.services.supabase_token_service import SupabaseJwtService
from tests.support.supabase_tokens import AUDIENCIA, EMISOR, ClavesDePrueba


@pytest.fixture
def claves() -> ClavesDePrueba:
    return ClavesDePrueba()


@pytest.fixture
def verificador(claves: ClavesDePrueba) -> SupabaseJwtService:
    return SupabaseJwtService(
        jwks_source=claves.fuente_jwks,
        issuer=EMISOR,
        audience=AUDIENCIA,
    )


class TestTokenValido:
    async def test_devuelve_la_identidad_afirmada(self, verificador, claves):
        p = await verificador.verify(claves.token(sub="abc-123", email="A@Ejemplo.CL"))

        assert p.subject == "abc-123"
        assert p.email == "a@ejemplo.cl"  # normalizado, como la entidad User
        assert p.full_name == "Persona de Prueba"
        assert p.email_verified is True
        assert p.provider == "google"


class TestNombreDelUsuario:
    """Google manda `full_name`; otros proveedores y el registro por correo, no."""

    async def test_usa_full_name_cuando_viene(self, verificador, claves):
        t = claves.token(user_metadata={"full_name": "Ana Díaz"})
        assert (await verificador.verify(t)).full_name == "Ana Díaz"

    async def test_cae_a_name_si_no_hay_full_name(self, verificador, claves):
        t = claves.token(user_metadata={"name": "Ana Díaz"})
        assert (await verificador.verify(t)).full_name == "Ana Díaz"

    async def test_sin_ninguno_usa_la_parte_local_del_correo(self, verificador, claves):
        t = claves.token(email="ana.diaz@ejemplo.cl", user_metadata={})
        assert (await verificador.verify(t)).full_name == "ana.diaz"


class TestTokenRechazado:
    async def test_expirado(self, verificador, claves):
        with pytest.raises(InvalidToken):
            await verificador.verify(claves.token(expira_en=timedelta(seconds=-1)))

    async def test_emisor_distinto(self, verificador, claves):
        with pytest.raises(InvalidToken):
            await verificador.verify(claves.token(emisor="https://otro/auth/v1"))

    async def test_audiencia_distinta(self, verificador, claves):
        with pytest.raises(InvalidToken):
            await verificador.verify(claves.token(audiencia="otra-cosa"))

    @pytest.mark.parametrize("claim", ["sub", "exp", "aud", "iss"])
    async def test_sin_un_claim_obligatorio(self, verificador, claves, claim):
        with pytest.raises(InvalidToken):
            await verificador.verify(claves.token(omitir=(claim,)))

    async def test_firmado_por_otra_clave_con_el_mismo_kid(self, verificador, claves):
        """Un `kid` conocido no vale de nada si la firma no cuadra."""
        otras = ClavesDePrueba(kid=claves.kid)
        with pytest.raises(InvalidToken):
            await verificador.verify(claves.token(firmante=otras.privada))

    async def test_hs256_firmado_con_la_clave_publica(self, verificador, claves):
        """Confusión de algoritmo: la clave pública como secreto HMAC.

        El JWKS es público, así que si HS256 se aceptara, cualquiera podría
        emitir sesiones de cualquier usuario. Acá hay dos defensas superpuestas:
        el algoritmo del token se compara contra una lista fija, y la clave sale
        del JWKS ya tipada como asimétrica, así que nunca se le entrega a HMAC
        como si fueran bytes.

        Lo que este test asegura de verdad es que el rechazo llegue como
        `InvalidToken` —o sea, un 401— y no como una excepción cruda: PyJWT
        lanza un `TypeError` propio cuando el algoritmo y la clave no casan, y
        sin capturarlo esto sería un 500.
        """
        with pytest.raises(InvalidToken):
            await verificador.verify(claves.token_hs256())

    async def test_anonimo(self, verificador, claves):
        with pytest.raises(InvalidToken):
            await verificador.verify(claves.token(is_anonymous=True))

    async def test_rol_que_no_es_de_usuario_conectado(self, verificador, claves):
        """Cierra de paso los tokens de service_role, que no representan a nadie."""
        with pytest.raises(InvalidToken):
            await verificador.verify(claves.token(rol="service_role"))

    @pytest.mark.parametrize("basura", ["", "no-es-un-jwt", "a.b.c"])
    async def test_texto_que_no_es_un_token(self, verificador, basura):
        with pytest.raises(InvalidToken):
            await verificador.verify(basura)

    async def test_kid_que_no_esta_publicado(self, verificador, claves):
        with pytest.raises(InvalidToken):
            await verificador.verify(claves.token(kid="kid-inventado"))


class TestCacheDeClaves:
    async def test_no_se_descargan_en_cada_peticion(self, verificador, claves):
        await verificador.verify(claves.token())
        await verificador.verify(claves.token())
        assert claves.llamadas_al_jwks == 1

    async def test_un_kid_desconocido_fuerza_una_recarga(self, verificador, claves):
        """Supabase rota claves, y la nueva aparece con un `kid` que no tenemos."""
        await verificador.verify(claves.token())  # llena la caché
        assert claves.llamadas_al_jwks == 1

        claves.kid = "clave-rotada"
        claves.privada = ClavesDePrueba().privada
        await verificador.verify(claves.token())

        assert claves.llamadas_al_jwks == 2

    async def test_un_kid_desconocido_no_descarga_en_cada_intento(
        self, verificador, claves
    ):
        """Sin límite, mandar tokens con `kid` al azar nos vuelve un ariete.

        Cada petición inválida gatillaría una descarga contra Supabase desde
        nuestro propio backend. Dos llamadas y no una: la primera llena la caché
        vacía y la segunda es el único intento que se concede por ventana, por
        si la clave acabara de rotar. Las otras tres no salen a la red.
        """
        for _ in range(5):
            with pytest.raises(InvalidToken):
                await verificador.verify(claves.token(kid="kid-inventado"))

        assert claves.llamadas_al_jwks == 2

    async def test_pasado_el_ttl_se_vuelven_a_pedir(self, claves):
        reloj = {"t": 1000.0}
        v = SupabaseJwtService(
            jwks_source=claves.fuente_jwks,
            issuer=EMISOR,
            audience=AUDIENCIA,
            cache_seconds=600,
            reloj=lambda: reloj["t"],
        )

        await v.verify(claves.token())
        reloj["t"] += 601
        await v.verify(claves.token())

        assert claves.llamadas_al_jwks == 2
