from uuid import UUID


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


class UserAlreadyHasSupplier(Exception):
    def __init__(self, user_id: UUID):
        super().__init__("Ya tienes una empresa registrada")
        self.user_id = user_id


class SupplierNotFoundForUser(Exception):
    def __init__(self, user_id: UUID):
        super().__init__(f"No se encontró un perfil de proveedor asociado al usuario {user_id}")
        self.user_id = user_id


class SupplierVectorNotFound(Exception):
    def __init__(self, supplier_id: UUID):
        super().__init__(f"No se encontró el vector para el proveedor {supplier_id} en el almacén vectorial")
        self.supplier_id = supplier_id
