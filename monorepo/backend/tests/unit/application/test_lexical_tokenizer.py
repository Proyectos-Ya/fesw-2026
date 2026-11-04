"""Pruebas unitarias para LexicalTokenizer (Plan 256, Fase 1)."""

import pytest

from app.application.services.lexical_tokenizer import (
    LexicalTokenizer,
    SparseTermVector,
    hash_term_to_uint32,
)


def test_hash_term_es_determinista_y_estable_entre_procesos():
    h1 = hash_term_to_uint32("jabon")
    h2 = hash_term_to_uint32("jabon")
    assert h1 == h2
    assert isinstance(h1, int)
    assert 0 <= h1 < (2**32)
    # Distintas palabras producen distintos hashes
    h3 = hash_term_to_uint32("cloro")
    assert h1 != h3


def test_normalizacion_remueve_tildes_y_convierte_a_minusculas():
    tok = LexicalTokenizer()
    terminos = tok.tokenize("Licitación de Fármacos y Químicos en Concepción")
    assert "licitacion" in terminos
    assert "farmacos" in terminos
    assert "quimicos" in terminos
    assert "concepcion" in terminos


def test_remueve_stopwords_y_palabras_cortas():
    tok = LexicalTokenizer()
    terminos = tok.tokenize("de la el en y a los las del por para con un una al se que o su sus lo")
    assert terminos == []


def test_stemming_ligero_unifica_plurales_y_sufijos():
    tok = LexicalTokenizer()
    # "medicamentos" -> "medicament", "medicamento" -> "medicament"
    assert tok.stem("medicamentos") == tok.stem("medicamento")
    # "reparaciones" y "reparacion" unifican a la misma raíz ("repara")
    assert tok.stem("reparaciones") == tok.stem("reparacion")
    assert tok.stem("reparaciones") == "repara"


def test_encode_sparse_retorna_indices_y_frecuencias_ordenadas():
    tok = LexicalTokenizer()
    texto = "Cloro desinfectante, cloro concentrado para limpieza"
    sparse = tok.encode_sparse(texto)

    assert isinstance(sparse, SparseTermVector)
    assert len(sparse.indices) == len(sparse.values)
    assert len(sparse.indices) > 0
    # Los índices deben ser estrictamente crecientes para sparse vectors en Qdrant
    assert sparse.indices == sorted(sparse.indices)
    assert len(set(sparse.indices)) == len(sparse.indices)

    # "cloro" aparece dos veces, su valor debe ser mayor o proporcional
    idx_cloro = hash_term_to_uint32(tok.stem("cloro"))
    pos_cloro = sparse.indices.index(idx_cloro)
    assert sparse.values[pos_cloro] == 2.0


def test_encode_sparse_con_texto_vacio_retorna_vector_vacio():
    tok = LexicalTokenizer()
    sparse = tok.encode_sparse("")
    assert sparse.indices == []
    assert sparse.values == []
