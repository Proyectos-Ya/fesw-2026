class ScoreMatchingNoEncontrado(Exception):
    def __init__(self, proveedor_id: str, licitacion_id: str) -> None:
        msg = (
            f"No existe score de matching para proveedor {proveedor_id}"
            f" y licitacion {licitacion_id}"
        )
        super().__init__(msg)
        self.proveedor_id = proveedor_id
        self.licitacion_id = licitacion_id


class ScoreCalculationError(Exception):
    """No se pudo calcular la compatibilidad de un par proveedor/licitación.

    Se lanza cuando el reranker no devuelve la candidata que se le mandó. Es un
    fallo de infraestructura, no un "no hay resultado": devolver un puntaje
    inventado sería peor, porque el usuario lo lee como una medición.
    """

    def __init__(self, proveedor_id: str, licitacion_id: str) -> None:
        msg = (
            f"No se pudo calcular la compatibilidad del proveedor {proveedor_id}"
            f" con la licitacion {licitacion_id}"
        )
        super().__init__(msg)
        self.proveedor_id = proveedor_id
        self.licitacion_id = licitacion_id
