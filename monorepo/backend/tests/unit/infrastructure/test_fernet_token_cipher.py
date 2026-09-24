import pytest
from cryptography.fernet import Fernet

from app.infrastructure.services.security.fernet_token_cipher import (
    FernetTokenCipher,
    TokenDecryptionError,
)

LLAVE = Fernet.generate_key().decode()
OTRA_LLAVE = Fernet.generate_key().decode()


def test_cifra_y_descifra_el_mismo_texto():
    cipher = FernetTokenCipher(LLAVE)

    cifrado = cipher.encrypt("ya29.token-secreto")

    assert cifrado != "ya29.token-secreto"
    assert "token-secreto" not in cifrado
    assert cipher.decrypt(cifrado) == "ya29.token-secreto"


def test_dos_cifrados_del_mismo_texto_son_distintos():
    cipher = FernetTokenCipher(LLAVE)

    assert cipher.encrypt("igual") != cipher.encrypt("igual")


def test_con_otra_llave_no_se_puede_descifrar():
    cifrado = FernetTokenCipher(LLAVE).encrypt("secreto")

    with pytest.raises(TokenDecryptionError):
        FernetTokenCipher(OTRA_LLAVE).decrypt(cifrado)


def test_rota_la_llave_sin_perder_lo_ya_cifrado():
    # La llave nueva va primero: cifra con ella y aún descifra con la anterior.
    cifrado_viejo = FernetTokenCipher(LLAVE).encrypt("secreto")
    rotado = FernetTokenCipher(f"{OTRA_LLAVE},{LLAVE}")

    assert rotado.decrypt(cifrado_viejo) == "secreto"
    assert FernetTokenCipher(OTRA_LLAVE).decrypt(rotado.encrypt("nuevo")) == "nuevo"


@pytest.mark.parametrize("llave", ["", "  ", "no-es-una-llave-fernet"])
def test_rechaza_llaves_invalidas(llave: str):
    with pytest.raises(ValueError):
        FernetTokenCipher(llave)
