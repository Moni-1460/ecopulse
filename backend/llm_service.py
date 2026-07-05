"""
llm_service.py
---------------
All prompt-engineering and LLM-API integration lives here, isolated from the
web layer so the "prompting strategy" can be iterated on independently.

Provider: Groq (OpenAI-compatible /chat/completions endpoint). Swapping to
another provider (Gemini, OpenAI, Anthropic) only requires changing
`_call_llm`; every function above it deals purely in plain Python data.

Prompt-engineering techniques applied:
1. Role / persona priming        -> SYSTEM_PROMPT gives the model a fixed
                                     expert identity and non-negotiable rules.
2. Domain constraint fencing      -> the model is explicitly restricted to
                                     the sustainable-living niche and told
                                     how to redirect off-topic requests.
3. Structured output contract     -> the model is required to answer with a
                                     single JSON object matching an exact
                                     schema, so the API layer never has to
                                     parse free text.
4. Few-shot exemplars              -> a small curated set of gold examples is
                                     always included; retrieved top-rated
                                     past generations are appended as
                                     *additional* few-shot examples,
                                     turning user feedback into a live,
                                     lightweight retrieval-augmented loop.
5. Platform-aware constraints      -> per-platform rules (length, hashtag
                                     count, emoji usage) are injected
                                     dynamically instead of baked in once,
                                     so one prompt template serves 4 very
                                     different channels.
6. Silent reasoning instruction    -> the model is told to plan internally
                                     but reveal only the final JSON, which
                                     keeps output clean without needing a
                                     separate parsing step for chain-of-thought.
"""

import os
import json
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

NICHE = "sustainable living, eco-friendly habits, and everyday climate action"

PLATFORM_RULES = {
    "twitter": "Max 260 characters total. 1-2 short punchy sentences. 2-3 hashtags. At most 1 emoji.",
    "instagram": "150-300 characters, warm and visual language that suggests an accompanying photo. "
                 "5-8 hashtags. 2-4 emojis used naturally.",
    "linkedin": "500-900 characters. Professional, insight-driven tone, may include one line-broken list. "
                "2-4 hashtags. 0-1 emoji, used sparingly.",
    "facebook": "300-500 characters, conversational and community-oriented, inviting comments/shares. "
                "3-5 hashtags. 1-3 emojis.",
}

SYSTEM_PROMPT = f"""You are EcoPulse, an expert social media strategist who writes ONLY about
{NICHE}. You have years of experience growing sustainability-focused brand accounts.

NON-NEGOTIABLE RULES:
- Stay strictly within the sustainable-living niche. If a requested topic is unrelated to
  sustainability, the environment, or eco-friendly living, reinterpret it by finding the closest
  authentic sustainability angle rather than refusing.
- Never invent statistics, scientific claims, or citations. Prefer actionable, verifiable, everyday
  advice over big numeric claims.
- Never use guilt-tripping, doom-laden, or shaming language. The voice is encouraging and practical,
  never preachy.
- Avoid generic filler ("in today's world", "now more than ever"). Every line must earn its place.
- Follow the platform-specific formatting rules you are given exactly (length, hashtag count, emoji use).
- Think through audience, hook, and structure privately, but output NOTHING except the final JSON object.

OUTPUT CONTRACT:
Respond with ONE JSON object and nothing else -- no markdown fences, no preamble, no explanation.
The JSON object must have exactly these keys:
{{
  "content": "<the post body text, following the platform rules>",
  "hashtags": "<comma-separated hashtags, no # symbol duplicated, lowercase, no spaces>",
  "cta": "<a single short call-to-action sentence appropriate for the platform>"
}}
"""

# A small, curated few-shot bank: always-available gold examples per platform+tone
# combination so first-time users (before any post history exists) still get
# high quality, on-brand generations.
FEW_SHOT_BANK = [
    {
        "platform": "instagram", "tone": "inspirational",
        "topic": "starting a windowsill herb garden",
        "content": "Your first basil leaf will feel bigger than it looks 🌱 A windowsill garden "
                    "turns a few pots of soil into fresher meals, less packaging, and five minutes "
                    "of quiet every morning.",
        "hashtags": "windowsillgarden,growyourown,sustainableliving,ecofriendlyhome,smallwins",
        "cta": "Tell us what you're growing this month 👇",
    },
    {
        "platform": "twitter", "tone": "informative",
        "topic": "reducing food waste at home",
        "content": "Freeze veggie scraps in one bag. Once it's full, simmer it into stock. "
                    "Zero waste, free flavor. ♻️",
        "hashtags": "foodwaste,zerowaste,sustainability",
        "cta": "Try it this week and see how far one bag goes.",
    },
    {
        "platform": "linkedin", "tone": "professional",
        "topic": "sustainable procurement for small businesses",
        "content": "Switching one supplier to a local, lower-packaging option rarely happens overnight -- "
                    "it starts with a single line item.\n\nLast quarter, three changes on our shortlist:\n"
                    "- Recycled-content packaging over virgin cardboard\n"
                    "- A regional supplier that cut delivery emissions by shortening the route\n"
                    "- Bulk ordering to reduce shipment frequency\n\n"
                    "None required a new budget line. All three required someone to ask the question.",
        "hashtags": "sustainableprocurement,smallbusiness,esg,supplychain",
        "cta": "What's one line item worth questioning on your next order?",
    },
    {
        "platform": "facebook", "tone": "humorous",
        "topic": "reusable bag habits",
        "content": "Me: I have 47 reusable bags at home. Also me, at the checkout: 'oh no, they're all "
                    "in the car.' 😅 If this is you too, you're not alone -- and one bag in your work bag "
                    "or coat pocket solves it for good.",
        "hashtags": "reusablebags,zerowastehumor,sustainableliving,ecotips",
        "cta": "Where do YOU keep your emergency bag? Comment below!",
    },
]


def _select_few_shots(platform: str, tone: str, limit: int = 2):
    """Pick the most relevant curated examples for this platform/tone pair."""
    exact = [e for e in FEW_SHOT_BANK if e["platform"] == platform and e["tone"] == tone]
    same_platform = [e for e in FEW_SHOT_BANK if e["platform"] == platform and e not in exact]
    chosen = (exact + same_platform)[:limit]
    if not chosen:
        chosen = FEW_SHOT_BANK[:limit]
    return chosen


def _format_examples(examples):
    blocks = []
    for ex in examples:
        blocks.append(
            f'Example (platform={ex["platform"]}, tone={ex["tone"]}, topic="{ex["topic"]}"):\n'
            f'{{"content": {json.dumps(ex["content"])}, '
            f'"hashtags": {json.dumps(ex["hashtags"])}, '
            f'"cta": {json.dumps(ex["cta"])}}}'
        )
    return "\n\n".join(blocks)


def build_prompt(topic: str, platform: str, tone: str, keywords: str | None,
                  retrieved_examples: list[dict] | None):
    """
    Assembles the final user-turn prompt. Curated few-shots are always
    included; retrieved top-rated past posts (real user feedback) are
    appended as extra, higher-priority examples -- this is the
    "retrieval-augmented" part of the pipeline.
    """
    curated = _select_few_shots(platform, tone)
    examples_text = _format_examples(curated)

    retrieved_text = ""
    if retrieved_examples:
        retrieved_text = (
            "\n\nThese examples were rated highly by the actual user for this exact "
            "platform/tone combination -- match their voice closely:\n\n"
            + _format_examples([
                {"platform": r["platform"], "tone": r["tone"], "topic": r["topic"],
                 "content": r["content"], "hashtags": r["hashtags"] or "",
                 "cta": r["cta"] or ""}
                for r in retrieved_examples
            ])
        )

    keywords_line = f'\nKeywords to weave in naturally if they fit: {keywords}' if keywords else ""

    user_prompt = f"""PLATFORM: {platform}
PLATFORM RULES: {PLATFORM_RULES[platform]}
TONE: {tone}
TOPIC ANGLE: {topic}{keywords_line}

Here are style examples to calibrate voice and format (do not copy content, only style/structure):

{examples_text}{retrieved_text}

Now write ONE new, original post for the TOPIC ANGLE above, following the OUTPUT CONTRACT exactly."""

    return user_prompt


class LLMError(Exception):
    pass


def _call_llm(system_prompt: str, user_prompt: str) -> dict:
    if not GROQ_API_KEY:
        raise LLMError(
            "GROQ_API_KEY is not set. Add it to your .env file (see .env.example) "
            "or export it as an environment variable before starting the server."
        )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 600,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
    except requests.RequestException as e:
        raise LLMError(f"Could not reach the Groq API: {e}")

    if resp.status_code != 200:
        raise LLMError(f"Groq API error ({resp.status_code}): {resp.text[:300]}")

    data = resp.json()
    try:
        raw_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError("Unexpected response shape from Groq API.")

    cleaned = raw_text.strip().strip("`")
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        raise LLMError("Model did not return valid JSON. Try generating again.")

    for key in ("content", "hashtags", "cta"):
        parsed.setdefault(key, "")

    return parsed


def generate_post(topic: str, platform: str, tone: str, keywords: str | None,
                   retrieved_examples: list[dict] | None = None) -> dict:
    """Public entry point used by the API layer."""
    user_prompt = build_prompt(topic, platform, tone, keywords, retrieved_examples)
    return _call_llm(SYSTEM_PROMPT, user_prompt)
