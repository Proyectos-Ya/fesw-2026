from typing import Optional
from pydantic import BaseModel, Field


class CreateSupplierSchema(BaseModel):
    rut: str = Field(max_length=12)
    legal_name: str = Field(max_length=255)
    trade_name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    regions: Optional[list[str]] = None
    sectors: Optional[list[str]] = None
    certifications: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    years_experience: Optional[int] = Field(default=None, ge=0)
    num_employees: Optional[int] = Field(default=None, ge=1)