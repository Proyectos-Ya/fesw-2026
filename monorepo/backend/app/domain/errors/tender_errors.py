from uuid import UUID


class TenderNotFound(Exception):
    """Excepción lanzada cuando una licitación no existe en el sistema."""

    def __init__(self, tender_id: UUID):
        super().__init__(f"Licitación con ID {tender_id} no encontrada")
        self.tender_id = tender_id


class InvalidSearchCriteria(Exception):
    """Los criterios de búsqueda no pueden cumplirse.

    Un rango invertido o un monto negativo no devuelven nada nunca. Fallar es
    mejor que responder con una lista vacía, que el usuario leería como "no hay
    licitaciones" en vez de "escribiste el filtro al revés".
    """

    def __init__(self, detalle: str) -> None:
        self.detalle = detalle
        super().__init__(detalle)


class TenderClosedForScoring(Exception):
    """No se calcula compatibilidad de una licitación cerrada.

    El puntaje existe para decidir si postular, y a una licitación cerrada ya no
    se postula. Gastar una inferencia ahí no le sirve a nadie.
    """

    def __init__(self, tender_id: UUID):
        super().__init__(
            f"La licitación {tender_id} ya cerró: no se calcula su compatibilidad"
        )
        self.tender_id = tender_id


class TenderClosedForAnalysis(Exception):
    """No se genera ni regenera el análisis IA de una licitación cerrada.

    Lo ya generado se sigue mostrando: sirve como registro de lo que se evaluó.
    """

    def __init__(self, tender_id: UUID):
        super().__init__(
            f"La licitación {tender_id} ya cerró: no se genera su análisis"
        )
        self.tender_id = tender_id
