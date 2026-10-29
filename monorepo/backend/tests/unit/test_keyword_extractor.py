"""Extracción léxica de palabras clave desde la descripción de una empresa."""

import unicodedata

from app.application.services.company_profiling.keyword_extractor import (
    MAX_SUGGESTIONS,
    suggest_keywords,
)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


class TestSuggestKeywords:
    def test_extrae_terminos_del_texto(self):
        result = suggest_keywords(
            "Instalación de luminarias LED y mantención de redes."
        )

        assert "luminarias LED" in result
        assert any("redes" in term for term in result)

    def test_conserva_las_tildes_del_texto_original(self):
        result = suggest_keywords("Ofrecemos reparación de electrodomésticos.")

        assert "reparación de electrodomésticos" in result

    def test_ninguna_sugerencia_empieza_ni_termina_en_una_stopword(self):
        result = suggest_keywords(
            "Somos una empresa que realiza obras de ingeniería para la minería y el transporte."
        )

        assert result
        for term in result:
            words = _fold(term).split()
            assert words[0] not in {"de", "la", "el", "y", "para", "una", "que", "en"}
            assert words[-1] not in {"de", "la", "el", "y", "para", "una", "que", "en"}

    def test_no_sugiere_palabras_de_relleno_sueltas(self):
        result = suggest_keywords(
            "Somos una empresa con años de experiencia y servicios de calidad."
        )

        assert "empresa" not in result
        assert "servicios" not in result
        assert "experiencia" not in result

    def test_no_repite_las_palabras_clave_que_ya_tiene(self):
        result = suggest_keywords(
            "Pintura y revestimiento de muros.", existing_keywords=["Pintura"]
        )

        assert "pintura" not in result
        assert "revestimiento" in result

    def test_compara_sin_tildes_ni_mayusculas_contra_las_existentes(self):
        result = suggest_keywords(
            "Mantención de equipos industriales.",
            existing_keywords=["MANTENCION DE EQUIPOS"],
        )

        assert "mantención de equipos" not in result

    def test_texto_vacio_devuelve_lista_vacia(self):
        assert suggest_keywords("") == []
        assert suggest_keywords("   \n ") == []

    def test_solo_stopwords_devuelve_lista_vacia(self):
        assert suggest_keywords("de la y en el para con los que") == []

    def test_solo_numeros_y_signos_devuelve_lista_vacia(self):
        assert suggest_keywords("2024 - 15% ... ???") == []

    def test_prioriza_los_terminos_del_diccionario_de_actividades(self):
        # "pintura" va al final del texto; sin prioridad saldría después de los otros.
        result = suggest_keywords(
            "Trabajamos con maderas nobles y estructuras metálicas livianas, además de pintura."
        )

        assert result[0] == "pintura"

    def test_devuelve_la_frase_del_diccionario_con_su_ortografia(self):
        result = suggest_keywords("Mantencion de areas verdes para municipios.")

        assert "mantención de áreas verdes" in result

    def test_prioriza_los_terminos_que_calzan_con_un_rubro_del_clasificador(self):
        result = suggest_keywords("Mesas de madera y servicios de limpieza.")

        assert result.index("servicios de limpieza") < result.index("mesas de madera")

    def test_no_repite_un_termino_que_aparece_varias_veces(self):
        result = suggest_keywords("Pintura, PINTURA y pintura.")

        assert result == ["pintura"]

    def test_no_devuelve_terminos_que_se_traslapan(self):
        result = suggest_keywords("Obras civiles menores.")

        assert "obras civiles" in result
        assert "civiles menores" not in result
        assert "obras civiles menores" not in result

    def test_los_terminos_son_palabras_completas_del_texto(self):
        text = (
            "Fabricación de estructuras metálicas y montaje de galpones industriales."
        )
        text_words = set(_fold(text).replace(".", "").split())

        result = suggest_keywords(text)

        assert result
        for term in result:
            assert 1 <= len(term.split()) <= 3
            assert set(_fold(term).split()) <= text_words

    def test_respeta_el_tope_de_sugerencias(self):
        words = [
            f"producto{chr(97 + i)}{chr(97 + j)}" for i in range(6) for j in range(6)
        ]
        result = suggest_keywords(", ".join(words))

        assert len(result) == MAX_SUGGESTIONS

    def test_es_determinista(self):
        text = "Venta de insumos médicos, servicio técnico y capacitación del personal."

        assert suggest_keywords(text) == suggest_keywords(text)
