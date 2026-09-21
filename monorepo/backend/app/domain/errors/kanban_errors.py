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

        
