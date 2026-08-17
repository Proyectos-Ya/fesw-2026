from uuid import UUID


class TenderNotFound(Exception):
    """Excepción lanzada cuando una licitación no existe en el sistema."""

    def __init__(self, tender_id: UUID):
        super().__init__(f"Licitación con ID {tender_id} no encontrada")
        self.tender_id = tender_id
