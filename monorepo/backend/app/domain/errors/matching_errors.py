class ScoreMatchingNoEncontrado(Exception):
    def __init__(self, proveedor_id: str, licitacion_id: str) -> None:
        msg = (
            f"No existe score de matching para proveedor {proveedor_id}"
            f" y licitacion {licitacion_id}"
        )
        super().__init__(msg)
        self.proveedor_id = proveedor_id
        self.licitacion_id = licitacion_id


class RecommendationsSaveError(Exception):
    """No se pudo guardar el ranking recién calculado de un proveedor.

    Es transitorio —la base rechazó la escritura, por ejemplo porque una
    licitación desapareció mientras se calculaba—, así que el mensaje invita a
    reintentar. Lo lee el usuario tal cual, por eso no lleva ids ni detalle SQL.
    """

    def __init__(self) -> None:
        super().__init__(
            "No pudimos guardar tus recomendaciones en este momento. "
            "Inténtalo nuevamente en unos segundos."
        )


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
