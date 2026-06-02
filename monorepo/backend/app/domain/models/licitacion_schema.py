from pydantic import BaseModel


class IngestRequest(BaseModel):
    estado: str = "activas"
    limit: int = 100
    offset: int = 0


class IngestResult(BaseModel):
    procesadas: int
    duplicadas: int
    errores: int
    version_modelo: str
