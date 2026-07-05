"""
schemas.py
----------
Pydantic models used to validate API input/output. Keeping these separate
from the ORM models means the API contract can evolve independently of the
database schema.
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

Platform = Literal["twitter", "instagram", "linkedin", "facebook"]
Tone = Literal["informative", "inspirational", "humorous", "professional"]


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=255,
                        description="A sustainable-living angle, e.g. 'composting for apartment dwellers'")
    platform: Platform = "instagram"
    tone: Tone = "inspirational"
    keywords: Optional[str] = Field(None, max_length=300,
                                     description="Comma-separated keywords to weave in, optional")
    use_past_examples: bool = Field(True, description="Retrieve top-rated past posts as few-shot examples")


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]


class ScheduleRequest(BaseModel):
    scheduled_at: datetime


class PostOut(BaseModel):
    id: int
    topic: str
    platform: str
    tone: str
    keywords: Optional[str]
    content: str
    hashtags: Optional[str]
    cta: Optional[str]
    rating: Optional[str]
    scheduled_at: Optional[str]
    created_at: Optional[str]

    class Config:
        from_attributes = True


class AnalyticsOut(BaseModel):
    total_posts: int
    by_platform: dict
    by_tone: dict
    upvotes: int
    downvotes: int
