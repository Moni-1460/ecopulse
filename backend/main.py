"""
main.py
-------
EcoPulse API server.

Serves:
- REST API under /api/*  (generation, history, feedback, scheduling, analytics)
- The static frontend (HTML/CSS/JS) from /frontend, so the whole project
  runs as a single deployable service (one Docker container, one port).
"""

import os
from collections import Counter
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
from dotenv import load_dotenv

load_dotenv()

from database import Base, engine, get_db
from models import Post
import schemas
import llm_service
import retrieval

os.makedirs("data", exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EcoPulse API",
    description="AI social media agent for sustainable-living content.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ecopulse"}


@app.post("/api/generate", response_model=schemas.PostOut)
def generate(req: schemas.GenerateRequest, db: Session = Depends(get_db)):
    retrieved = []
    if req.use_past_examples:
        retrieved = retrieval.retrieve_similar(db, req.platform, req.tone)

    try:
        result = llm_service.generate_post(
            topic=req.topic,
            platform=req.platform,
            tone=req.tone,
            keywords=req.keywords,
            retrieved_examples=retrieved,
        )
    except llm_service.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))

    post = Post(
        topic=req.topic,
        platform=req.platform,
        tone=req.tone,
        keywords=req.keywords,
        content=result["content"],
        hashtags=result["hashtags"],
        cta=result["cta"],
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post.to_dict()


@app.get("/api/posts", response_model=list[schemas.PostOut])
def list_posts(platform: str | None = None, tone: str | None = None,
               db: Session = Depends(get_db)):
    query = db.query(Post)
    if platform:
        query = query.filter(Post.platform == platform)
    if tone:
        query = query.filter(Post.tone == tone)
    posts = query.order_by(desc(Post.created_at)).all()
    return [p.to_dict() for p in posts]


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return {"deleted": post_id}


@app.post("/api/posts/{post_id}/feedback", response_model=schemas.PostOut)
def rate_post(post_id: int, req: schemas.FeedbackRequest, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.rating = req.rating
    db.commit()
    db.refresh(post)
    return post.to_dict()


@app.post("/api/posts/{post_id}/schedule", response_model=schemas.PostOut)
def schedule_post(post_id: int, req: schemas.ScheduleRequest, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.scheduled_at = req.scheduled_at
    db.commit()
    db.refresh(post)
    return post.to_dict()


@app.get("/api/analytics", response_model=schemas.AnalyticsOut)
def analytics(db: Session = Depends(get_db)):
    posts = db.query(Post).all()
    by_platform = Counter(p.platform for p in posts)
    by_tone = Counter(p.tone for p in posts)
    upvotes = sum(1 for p in posts if p.rating == "up")
    downvotes = sum(1 for p in posts if p.rating == "down")
    return {
        "total_posts": len(posts),
        "by_platform": dict(by_platform),
        "by_tone": dict(by_tone),
        "upvotes": upvotes,
        "downvotes": downvotes,
    }


# --- Serve the static frontend last, so it doesn't shadow /api routes ---
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
