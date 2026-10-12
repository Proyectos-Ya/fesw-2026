from uuid import UUID

from app.application.use_cases.proposals.generate_proposal import (
    GenerateProposalUseCase,
)
from app.domain.entities.proposal import ProposalDraft
from app.domain.errors.deep_analysis_errors import InvalidPromptInstruction
from app.shared.prompt_guard import frase_de_inyeccion


class RegenerateProposalUseCase:
    """Vuelve a redactar un borrador ya redactado con instrucciones libres (CA4).

    Por ejemplo "tono más formal" o "más énfasis en la experiencia en colegios".
    Las instrucciones pasan primero por el filtro de prompt injection, antes de
    gastar una llamada a la IA. Después es la misma redacción de B4, con las
    mismas fuentes, advertencias y guardrails.
    """

    def __init__(self, generate_use_case: GenerateProposalUseCase):
        self.generate_use_case = generate_use_case

    async def execute(
        self,
        user_id: UUID,
        supplier_id: UUID | None,
        tender_id: UUID,
        instructions: str,
    ) -> ProposalDraft:
        frase = frase_de_inyeccion(instructions)
        if frase is not None:
            raise InvalidPromptInstruction(
                "Las instrucciones contienen una frase no permitida: "
                f"'{frase}'. Describe solo cómo quieres ajustar el borrador."
            )
        return await self.generate_use_case.execute(
            user_id=user_id,
            supplier_id=supplier_id,
            tender_id=tender_id,
            instructions=instructions,
            require_ready=True,
        )
