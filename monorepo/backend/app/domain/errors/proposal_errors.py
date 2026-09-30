class InvalidProposalTransition(Exception):
    """La acción no corresponde al estado del borrador.

    Por ejemplo, responder mientras hay una discrepancia sin decidir, decidir sin
    que haya una, o redactar con preguntas pendientes. La API la traduce a 409.
    """

    def __init__(self, status: str, action: str):
        super().__init__(f"No se puede {action} un borrador en estado {status}.")
        self.status = status
        self.action = action


class ProposalDraftNotFound(Exception):
    """La empresa todavía no inició la postulación a esta licitación. La API da 404."""

    def __init__(self, tender_id: object):
        super().__init__(
            f"No hay una postulación iniciada para la licitación {tender_id}."
        )
        self.tender_id = tender_id


class QuestionNotInProposal(Exception):
    """La pregunta no corresponde a ninguna exigencia de esta postulación. La API da 404.

    Para responder una pregunta del banco fuera de una postulación está
    `/capabilities/questions/{id}/answer`.
    """

    def __init__(self, question_id: object):
        super().__init__(f"La pregunta {question_id} no es parte de esta postulación.")
        self.question_id = question_id
