from uuid import UUID


class SavedTenderNotFound(Exception):
    """Excepción lanzada cuando el usuario no tiene guardada esa licitación."""

    def __init__(self, user_id: UUID, tender_id: UUID):
        super().__init__(
            f"La licitación con ID {tender_id} no está en la lista de guardadas del usuario {user_id}"
        )
        self.user_id = user_id
        self.tender_id = tender_id
