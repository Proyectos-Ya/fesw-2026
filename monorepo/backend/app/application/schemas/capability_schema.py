from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class AnswerCapabilityInput(BaseModel):
    """Respuesta a una pregunta del banco.

    Sin `supplier_id` ni `tender_id`: la empresa sale de la sesión y la
    licitación de origen la fija el flujo de postulación, no el cliente.
    `extra="forbid"` rechaza a quien siga mandándolos, en vez de ignorarlos.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=500)
    # Vigencia de lo respondido, por ejemplo una certificación que vence. Con
    # zona obligatoria: sin ella no se sabe si es UTC u hora de Chile.
    valid_until: AwareDatetime | None = None


class AddCapabilityEvidenceInput(BaseModel):
    """Proyecto que respalda un "Sí" de experiencia.

    Sin `origin`: por esta vía toda evidencia es `manual`. Las importadas de
    Mercado Público entrarán por el backend (plan 230, §5 punto 10).
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    year: int
    buyer: str | None = Field(default=None, max_length=255)
    amount_clp: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=2000)
