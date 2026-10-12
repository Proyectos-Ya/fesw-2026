from uuid import UUID

class KanbanColumnNotFound(Exception):
    def __init__(self, column_id: UUID):
        super().__init__(f"Columna con ID {column_id} no se ha encontrado.")
        self.column_id = column_id

class KanbanCardNotFound(Exception):
    def __init__(self, user_id: UUID, tender_id: UUID):
        super().__init__(f"La licitación {tender_id} no está en el tablero del usuario {user_id}.")
        self.user_id = user_id
        self.tender_id = tender_id

class TenderAlreadyOnBoard(Exception):
    def __init__(self, user_id: UUID, tender_id: UUID):
        super().__init__(f"La licitación {tender_id} ya se encuentra en el tablero del usuario {user_id}.")
        self.user_id = user_id
        self.tender_id = tender_id


class ArchiveNotRestorable(Exception):
    """Las tarjetas auto-archivadas (`auto_3m`) no se pueden restaurar: la
    regla de negocio de CA4 permite restaurar solo lo que el usuario archivó
    a mano. Lo auto-archivado queda en el historial como registro."""

    def __init__(self, card_id: UUID, reason: str):
        super().__init__(
            f"La tarjeta {card_id} no se puede restaurar porque fue archivada "
            f"automáticamente ({reason})."
        )
        self.card_id = card_id
        self.reason = reason

