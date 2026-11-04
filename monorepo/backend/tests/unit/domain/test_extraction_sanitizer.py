"""Tests de saneamiento de texto y JSON de extracciones (plan 233, decisión 4)."""

from app.domain.services.extraction_sanitizer import sanear_extraccion, sanear_texto


def test_sanear_etiquetas_y_escapes():
    assert sanear_texto("<b>Hola</b> mundo") == "Hola mundo"
    assert sanear_texto("&lt;script&gt;alert(1)&lt;/script&gt;") == "alert(1)"
    assert sanear_texto("monto < 5 UTM") == "monto ‹ 5 UTM"


def test_sanear_urls_y_enlaces():
    assert sanear_texto("Postula en https://evil.test/x ya") == "Postula en [enlace omitido] ya"
    assert sanear_texto("Visita www.evil.cl ahora") == "Visita [enlace omitido] ahora"
    assert sanear_texto("Descarga de evil.com/ruta archivo") == "Descarga de [enlace omitido] archivo"
    assert sanear_texto("Enlace javascript:alert(1)") == "Enlace [enlace omitido]"
    # Los correos legítimos no son URLs y no se tocan
    assert sanear_texto("escribe a adquisiciones@municatemu.cl") == "escribe a adquisiciones@municatemu.cl"


def test_sanear_caracteres_de_control():
    assert sanear_texto("\x00a\u202eb") == "ab"


def test_sanear_extraccion_recorta_listas_y_largos():
    crudo = {
        "requisitos": [{"descripcion": "Req " + str(i)} for i in range(45)],
        "citas": [{"cita": "a" * 700, "verificada": True}],
        "fecha": "2026-10-05",
        "hora": "15:00",
        "tipo": "tecnico",
    }
    saneado = sanear_extraccion(crudo)
    assert isinstance(saneado, dict)
    # Lista recortada a máximo 40
    assert len(saneado["requisitos"]) == 40
    # Cita recortada a 600 caracteres con '…' al final
    cita_saneada = saneado["citas"][0]["cita"]
    assert len(cita_saneada) <= 600
    assert cita_saneada.endswith("…")
    # 'verificada' eliminada
    assert "verificada" not in saneado["citas"][0]
    # 'fecha', 'hora' y 'tipo' no tocados
    assert saneado["fecha"] == "2026-10-05"
    assert saneado["hora"] == "15:00"
    assert saneado["tipo"] == "tecnico"
