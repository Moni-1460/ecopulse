"""
retrieval.py
------------
A deliberately lightweight "retrieval" layer: it pulls the user's own
top-rated (👍) past posts that match the requested platform/tone, and hands
them to llm_service as extra few-shot examples.

This satisfies the spirit of the "vector DB" requirement (retrieval-augmented
generation based on semantic similarity of past content) without pulling in
a heavy embedding model for a course project. It is intentionally written as
a swappable module -- see README "Upgrading to a real vector DB" for how to
replace `retrieve_similar` with a Chroma/FAISS/Pinecone-backed version that
embeds `topic` and does a cosine-similarity search instead of exact
platform/tone matching.
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import Post


def retrieve_similar(db: Session, platform: str, tone: str, limit: int = 2):
    rows = (
        db.query(Post)
        .filter(Post.platform == platform, Post.tone == tone, Post.rating == "up")
        .order_by(desc(Post.created_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "platform": r.platform,
            "tone": r.tone,
            "topic": r.topic,
            "content": r.content,
            "hashtags": r.hashtags,
            "cta": r.cta,
        }
        for r in rows
    ]
