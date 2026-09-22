"""Claves y tokens de prueba que imitan lo que emite Supabase Auth.

Permite ejercitar el verificador **real** —firma, emisor, audiencia, vigencia,
algoritmo— sin levantar Supabase ni tocar la red: lo único que se sustituye es
de dónde salen las claves públicas. Un doble del verificador probaría el
aprovisionamiento pero no que sepamos rechazar un token falsificado, que es
justamente lo que no puede fallar.
"""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

EMISOR = "https://supabase-de-pruebas.local/auth/v1"
AUDIENCIA = "authenticated"


def _jwk_publico(clave: ec.EllipticCurvePrivateKey, kid: str) -> dict[str, Any]:
    return {
        **ECAlgorithm.to_jwk(clave.public_key(), as_dict=True),
        "kid": kid,
        "use": "sig",
        "alg": "ES256",
    }


class ClavesDePrueba:
    """Un par ES256 con el que firmar tokens y el JWKS que lo publica.

    `fuente_jwks` cuenta sus llamadas: así los tests pueden afirmar que las
    claves se cachean y que un `kid` desconocido no dispara una descarga por
    cada petición.
    """

    def __init__(self, kid: str = "clave-de-pruebas") -> None:
        self.kid = kid
        self.privada = ec.generate_private_key(ec.SECP256R1())
        self.llamadas_al_jwks = 0

    @property
    def jwks(self) -> dict[str, Any]:
        return {"keys": [_jwk_publico(self.privada, self.kid)]}

    async def fuente_jwks(self) -> dict[str, Any]:
        self.llamadas_al_jwks += 1
        return self.jwks

    def token(
        self,
        *,
        sub: str = "11111111-1111-4111-8111-111111111111",
        email: str = "persona@ejemplo.cl",
        user_metadata: dict[str, Any] | None = None,
        expira_en: timedelta = timedelta(hours=1),
        emisor: str = EMISOR,
        audiencia: str = AUDIENCIA,
        rol: str = "authenticated",
        firmante: ec.EllipticCurvePrivateKey | None = None,
        kid: str | None = None,
        omitir: tuple[str, ...] = (),
        **claims_extra: Any,
    ) -> str:
        """Firma un token con la forma de los que emite Supabase.

        `omitir` saca claims obligatorios para probar que se exigen; `firmante`
        y `kid` permiten simular una clave que no es la publicada.
        """
        ahora = datetime.now(UTC)
        claims: dict[str, Any] = {
            "sub": sub,
            "email": email,
            "aud": audiencia,
            "iss": emisor,
            "role": rol,
            "iat": ahora,
            "exp": ahora + expira_en,
            "is_anonymous": False,
            "app_metadata": {"provider": "google", "providers": ["google"]},
            "user_metadata": user_metadata
            if user_metadata is not None
            else {"full_name": "Persona de Prueba", "email_verified": True},
            **claims_extra,
        }
        for clave in omitir:
            claims.pop(clave, None)

        return jwt.encode(
            claims,
            firmante if firmante is not None else self.privada,
            algorithm="ES256",
            headers={"kid": kid if kid is not None else self.kid},
        )

    def token_hs256(self, **kwargs: Any) -> str:
        """Token HMAC forjado con la clave **pública** usada como secreto.

        Es el ataque de confusión de algoritmo: la clave pública la entrega el
        JWKS a quien la pida, así que si el verificador aceptara HS256 junto a
        los algoritmos asimétricos, cualquiera podría emitir sesiones.

        Se arma a mano y no con `jwt.encode` porque PyJWT se niega a firmar un
        HMAC con material asimétrico. Esa negativa es una defensa del lado de
        quien firma; acá hace falta producir el token que un atacante sí puede
        construir, para comprobar la defensa del lado de quien verifica.
        """
        pem = self.privada.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        ahora = datetime.now(UTC)
        claims = {
            "sub": "22222222-2222-4222-8222-222222222222",
            "email": "intruso@ejemplo.cl",
            "aud": AUDIENCIA,
            "iss": EMISOR,
            "role": "authenticated",
            "exp": int((ahora + timedelta(hours=1)).timestamp()),
            **kwargs,
        }

        def b64(datos: bytes) -> bytes:
            return base64.urlsafe_b64encode(datos).rstrip(b"=")

        cabecera = b64(
            json.dumps({"alg": "HS256", "typ": "JWT", "kid": self.kid}).encode()
        )
        cuerpo = b64(json.dumps(claims).encode())
        firmado = cabecera + b"." + cuerpo
        firma = b64(hmac.new(pem, firmado, hashlib.sha256).digest())
        return (firmado + b"." + firma).decode()
