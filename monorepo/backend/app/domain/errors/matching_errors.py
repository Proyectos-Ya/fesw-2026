class ScoreMatchingNoEncontrado(Exception):
    def __init__(self, proveedor_id: str, licitacion_id: str) -> None:
        msg = (
            f"No existe score de matching para proveedor {proveedor_id}"
            f" y licitacion {licitacion_id}"
        )
        super().__init__(msg)
        self.proveedor_id = proveedor_id
        self.licitacion_id = licitacion_id
