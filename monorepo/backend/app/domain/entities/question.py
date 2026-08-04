from typing import Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

class Question(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    provider_id: UUID
    discrepancy_type: Optional[str] = "Category"
    tender_requirement: Optional[str] = None
    question: str
    target_profile_field: str
    
    answered: bool = False
    answer: Optional[str] = None
    omitted: bool = False
    
    generated_at: UtcDateTime = Field(default_factory=utc_now_naive)
    answered_at: Optional[UtcDateTime] = None
    
    target_category: str = "general"
    options: List[str] = []