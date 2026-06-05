from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    estado: str = "activas"
    limit: int = Field(default=100, ge=1)
    offset: int = Field(default=0, ge=0)


class IngestResult(BaseModel):
    procesadas: int
    duplicadas: int
    errores: int
    version_modelo: str
