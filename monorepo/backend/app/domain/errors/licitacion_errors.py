class LicitacionNoEncontrada(Exception):
    def __init__(self, identifier: str):
        super().__init__(f"Licitacion con identificador '{identifier}' no encontrada")
        self.identifier = identifier


class LicitacionYaExiste(Exception):
    def __init__(self, codigo_externo: str):
        msg = f"Ya existe una licitacion con código externo {codigo_externo}"
        super().__init__(msg)
        self.codigo_externo = codigo_externo
