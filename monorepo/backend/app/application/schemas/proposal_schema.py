from app.domain.entities.proposal import ProposalDraft


class ProposalDraftView(ProposalDraft):
    """El borrador tal como lo ve la API.

    `is_expired` no se guarda: se calcula al leer con `Tender.esta_cerrada()`,
    así ninguna lectura tiene que escribir. Un borrador vencido se sigue
    mostrando, pero ya no se puede avanzar.
    """

    is_expired: bool = False
