"""Datos de una empresa obtenidos desde una fuente externa a partir de su RUT.

Dos momentos distintos, dos entidades:

* `CompanyRecord` es lo que **cualquier** fuente (SRE, Web Empresario) sabe de la
  empresa, ya traducido a una forma común. Cada adaptador se encarga de su propio
  esquema JSON; de acá en adelante nadie sabe de qué API vino el dato.
* `CompanyProfileDraft` es el borrador de perfil que se le sugiere al usuario en
  el wizard: regiones, rubros y palabras clave. Es una sugerencia editable, nunca
  el perfil final.
"""

from pydantic import BaseModel, Field


class EconomicActivity(BaseModel):
    """Una actividad económica registrada en el SII (código de 6 dígitos)."""

    code: int
    # Glosa tal como la entregó la fuente. Vacía cuando la fuente solo manda el
    # código (SRE).
    description: str = ""


class CompanyRecord(BaseModel):
    source: str
    rut: str
    legal_name: str = ""
    activities: list[EconomicActivity] = Field(default_factory=list)
    # Regiones tal como las escribe la fuente ("XIII REGION METROPOLITANA"), sin
    # normalizar. Vacía cuando la fuente no entrega domicilio (SRE).
    raw_regions: list[str] = Field(default_factory=list)
    # `None` cuando la fuente no informa término de giro.
    is_active: bool | None = None


class CompanyProfileDraft(BaseModel):
    source: str
    rut: str
    legal_name: str
    is_active: bool | None = None
    # Nombres de región del wizard ("Metropolitana", "O'Higgins").
    regions: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    # Avisos para el usuario sobre lo que no se pudo deducir.
    notices: list[str] = Field(default_factory=list)
