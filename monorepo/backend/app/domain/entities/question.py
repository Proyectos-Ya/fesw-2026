from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

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
    
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    answered_at: Optional[datetime] = None
    
    target_category: str = "general"
    options: List[str] = []