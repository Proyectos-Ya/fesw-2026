from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.proposal import DecisionAction, ProposalDraft


class ProposalDraftView(ProposalDraft):
    """El borrador tal como lo ve la API.

    `is_expired` no se guarda: se calcula al leer con `Tender.esta_cerrada()`,
    así ninguna lectura tiene que escribir. Un borrador vencido se sigue
    mostrando, pero ya no se puede avanzar.
    """

    is_expired: bool = False


class AnswerProposalQuestionInput(BaseModel):
    """Respuesta a una pregunta de la postulación.

    Sin `supplier_id`: la empresa sale de la sesión. `extra="forbid"` rechaza a
    quien lo mande.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=500)


class DecideDiscrepancyInput(BaseModel):
    """Decisión ante un "No" a una exigencia excluyente (CA8, CA9).

    `requirement_id` es la exigencia que el usuario vio en el aviso: si la pausa
    ya es otra, la API responde 409 en vez de decidir sobre algo que no vio.
    """

    model_config = ConfigDict(extra="forbid")

    requirement_id: str = Field(min_length=1)
    action: DecisionAction


class RegenerateProposalInput(BaseModel):
    """Instrucciones libres para volver a redactar el borrador (CA4)."""

    model_config = ConfigDict(extra="forbid")

    instructions: str = Field(min_length=1, max_length=1000)
