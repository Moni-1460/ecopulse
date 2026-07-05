# EcoPulse — Sustainable Living Social Media Agent

An AI agent that plans and drafts social media posts for a **sustainable
living / eco-friendly habits** brand voice. Give it a topic angle, a
platform, and a tone; it returns a ready-to-post caption, hashtags, and a
call-to-action — then learns your taste over time from the posts you rate.

This is an individual course project. **Unique topic niche: sustainable
living & everyday climate action** (as opposed to a generic multi-purpose
social copywriter).

---

## What it demonstrates (mapped to requirements)

| Requirement | How it's met |
|---|---|
| Prompt engineering | `backend/llm_service.py` — persona priming, niche fencing, strict JSON output contract, platform-aware constraints, curated + retrieved few-shot examples |
| LLM API | [Groq](https://console.groq.com) chat-completions API (`llama-3.3-70b-versatile`), OpenAI-compatible endpoint |
| Database | SQLite via SQLAlchemy (`backend/models.py`, `database.py`); doubles as the "memory" that feeds the retrieval step |
| Retrieval / vector-DB spirit | `backend/retrieval.py` pulls the user's own top-rated past posts per platform+tone as extra few-shot examples — a lightweight RAG loop; see "Upgrading to a real vector DB" below |
| Web framework | FastAPI (Python) serving a REST API |
| Frontend | Plain HTML/CSS/JavaScript, no build step, in `frontend/` |
| Deployment | `Dockerfile` + `docker-compose.yml` — one command to run anywhere (local, AWS ECS/EC2, Azure Container Apps, etc.) |

---

## Project structure

```
ecopulse/
├── backend/
│   ├── main.py          # FastAPI app: routes + serves the frontend
│   ├── llm_service.py    # All prompt engineering + Groq API calls
│   ├── retrieval.py      # Pulls top-rated past posts as few-shot examples
│   ├── models.py         # SQLAlchemy Post model
│   ├── schemas.py        # Pydantic request/response contracts
│   ├── database.py       # DB engine/session setup
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Running locally (no Docker)

Requires Python 3.11+.

```bash
cd ecopulse
cp .env.example .env
# edit .env and paste your free Groq API key (https://console.groq.com/keys)

cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — the FastAPI app serves the frontend directly,
so there's nothing else to start.

---

## Running with Docker

```bash
cd ecopulse
cp .env.example .env
# edit .env with your GROQ_API_KEY

docker compose up --build
```

Open **http://localhost:8000**. Posts persist in the `ecopulse-data` Docker
volume between restarts.

### Deploying to the cloud
- **AWS**: push the built image to ECR, run it on ECS Fargate or a single
  EC2 instance with `docker compose up -d`; put the `.env` values in the
  task definition's environment section (or AWS Secrets Manager).
- **Azure**: push to Azure Container Registry and deploy with Azure
  Container Apps or App Service for Containers; set `GROQ_API_KEY` as an
  app setting.
- **Any VM**: `docker compose up -d --build` behind an nginx/Caddy reverse
  proxy for TLS.

---

## API reference

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/generate` | Generate a new post (topic, platform, tone, keywords) |
| GET | `/api/posts` | List saved posts (optional `?platform=` `&tone=` filters) |
| DELETE | `/api/posts/{id}` | Delete a post |
| POST | `/api/posts/{id}/feedback` | Rate a post `{"rating": "up"|"down"}` |
| POST | `/api/posts/{id}/schedule` | Attach a scheduled datetime to a post |
| GET | `/api/analytics` | Totals by platform/tone and up/downvote counts |
| GET | `/api/health` | Liveness check |

Interactive OpenAPI docs are auto-generated at **`/docs`**.

---

## The prompt engineering, in detail

`llm_service.py` builds a two-part prompt every time:

1. **System prompt** — fixes the model's persona ("EcoPulse, an expert
   sustainable-living social strategist"), hard rules (stay in-niche, no
   invented statistics, no guilt-tripping tone, no filler phrases), and a
   strict JSON output contract so the API never has to parse loose text.
2. **User prompt** — assembled per-request from:
   - the platform's specific length/hashtag/emoji rules (one template, four
     very different channels),
   - 1-2 curated gold-standard examples for that platform/tone pair,
   - 0-2 of the *user's own* highest-rated past posts for that same
     platform/tone, retrieved from the database (see below), which lets a
     user's 👍/👎 feedback actually reshape future generations.

## Upgrading to a real vector DB

`retrieval.py` currently matches on exact `platform + tone + rating=up`,
which is deliberately simple so the whole project runs with nothing but
SQLite. To upgrade it to true semantic retrieval:

1. Add an embeddings call (e.g. Groq/OpenAI embeddings, or a local
   `sentence-transformers` model) when a post is saved, store the vector
   alongside the row (or in Chroma/FAISS/Pinecone).
2. In `retrieve_similar`, embed the incoming `topic` and do a cosine-
   similarity search instead of the exact-match filter.
3. Everything downstream (`llm_service.build_prompt`) is unchanged — it
   just receives a list of example dicts, however they were found.

---

## Notes on the LLM provider

Groq was chosen for its generous free tier and very low latency, which
keeps the "Generate post" button feeling instant. Swapping providers only
requires changing `_call_llm` in `llm_service.py` (e.g. to Google Gemini's
`generateContent` endpoint) — every other function passes plain
Python dicts and never touches provider-specific request/response shapes.
