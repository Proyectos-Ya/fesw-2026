class CompanyLookupNotConfigured(Exception):
    """No hay ninguna fuente de datos de empresas configurada."""

    def __init__(self) -> None:
        super().__init__("La importación de datos de empresas no está disponible.")


class InvalidRutForLookup(Exception):
    """El RUT no pasa la validación del dígito verificador."""

    def __init__(self, rut: str) -> None:
        super().__init__(f"El RUT {rut} no es válido. Revisa el dígito verificador.")


class CompanyNotFoundInSource(Exception):
    """La fuente respondió, pero no tiene datos para ese RUT."""

    def __init__(self, rut: str) -> None:
        super().__init__(f"No encontramos datos para el RUT {rut}.")


class CompanyLookupUnavailable(Exception):
    """La fuente no respondió o respondió algo inutilizable (caída, cuota, credencial)."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            "No pudimos consultar los datos de tu empresa en este momento. "
            "Inténtalo más tarde o completa los datos a mano."
        )
        self.detail = detail
