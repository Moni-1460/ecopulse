"""
models.py
---------
ORM models for EcoPulse (the Sustainable Living Social Media Agent).

Post: every piece of generated content, its inputs, and its performance
signal (rating). Ratings are what let the retrieval step in llm_service.py
pull "known good" past posts back into the prompt as few-shot examples --
a lightweight retrieval-augmented-generation loop without needing a full
vector database.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)

    # Generation inputs
    topic = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)   # twitter | instagram | linkedin | facebook
    tone = Column(String(50), nullable=False)        # informative | inspirational | humorous | professional
    keywords = Column(String(500), nullable=True)

    # Generation outputs
    content = Column(Text, nullable=False)
    hashtags = Column(String(500), nullable=True)    # comma-separated
    cta = Column(String(255), nullable=True)         # call to action line

    # Feedback / scheduling
    rating = Column(String(10), nullable=True)       # "up" | "down" | None
    scheduled_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "topic": self.topic,
            "platform": self.platform,
            "tone": self.tone,
            "keywords": self.keywords,
            "content": self.content,
            "hashtags": self.hashtags,
            "cta": self.cta,
            "rating": self.rating,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
