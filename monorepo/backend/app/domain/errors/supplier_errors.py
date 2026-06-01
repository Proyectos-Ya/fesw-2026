class SupplierNotFound(Exception):
    def __init__(self, rut: str):
        super().__init__(f"Proveedor con RUT {rut} no encontrado")
        self.rut = rut


class SupplierAlreadyExists(Exception):
    def __init__(self, rut: str):
        super().__init__(f"Ya existe un proveedor con RUT {rut}")
        self.rut = rut

class SupplierValidationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)