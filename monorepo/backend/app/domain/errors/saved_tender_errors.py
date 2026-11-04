from uuid import UUID


class SavedTenderNotFound(Exception):
    """La licitación no está en la lista de guardadas del workspace (HU-18)."""

    def __init__(self, supplier_id: UUID, tender_id: UUID):
        super().__init__(
            f"La licitación con ID {tender_id} no está en la lista de "
            f"guardadas del workspace {supplier_id}"
        )
        self.supplier_id = supplier_id
        self.tender_id = tender_id
