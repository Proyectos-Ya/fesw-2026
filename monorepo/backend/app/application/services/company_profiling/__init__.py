"""Perfilamiento de una empresa a partir de sus actividades económicas del SII.

Portado del spike 1 (`spikes/spike-1/poc/perfilamiento/`). Lógica pura, sin red:

* `activity_catalog`: catálogo oficial del SII (674 códigos con su glosa).
* `activity_dictionary`: códigos curados a mano → rubros y palabras clave de compra.
* `sector_classifier`: respaldo de rubro por la glosa, para códigos no curados.
* `profile_builder`: arma el borrador de perfil desde un `CompanyRecord`.
"""
