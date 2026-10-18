"""
AI engine for StudySpark.

How it works:
  1. We build a careful prompt asking the AI for STRICT JSON.
  2. We call the provider configured in .env (Groq = free, no credit card!).
  3. We validate the JSON so the website never crashes on weird AI output.
  4. If no API key is configured yet, we run in DEMO MODE: a local, offline
     generator written in pure Python. It is not as smart as a real AI, but it
     lets you build and test the whole app for free before connecting a key.
"""

import json
import os
import random
import re

import requests

AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()
AI_MODEL = os.getenv("AI_MODEL")  # optional override

DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
}

MAX_NOTES_LENGTH = int(os.getenv("MAX_NOTES_LENGTH", "20000"))


class AIError(Exception):
    """Raised when the AI provider fails or returns unusable output."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_key() -> str:
    """Return the API key for the configured provider, or "" if none."""
    return {
        "groq": os.getenv("GROQ_API_KEY", ""),
        "gemini": os.getenv("GEMINI_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
    }.get(AI_PROVIDER, "")


def is_demo_mode() -> bool:
    """True when we should use the offline demo generator instead of a real AI API."""
    return AI_PROVIDER == "mock" or not _get_key()


def model_info() -> str:
    if is_demo_mode():
        return "demo mode (offline)"
    return f"{AI_PROVIDER} / {AI_MODEL or DEFAULT_MODELS.get(AI_PROVIDER, '?')}"


# ---------------------------------------------------------------------------
# Prompts — the secret sauce of every AI product
# ---------------------------------------------------------------------------

_SCHEMAS = {
    "flashcards": (
        '{"flashcards": [{"front": "question or term", "back": "answer or definition"}]}'
    ),
    "quiz": (
        '{"questions": [{"question": "...", "options": ["A", "B", "C", "D"], '
        '"answer_index": 0, "explanation": "why the answer is correct"}]}'
    ),
    "summary": (
        '{"overview": "2-3 sentence overview", "key_points": ["point 1", "point 2"], '
        '"key_terms": [{"term": "word", "definition": "meaning"}]}'
    ),
}

_SYSTEM = (
    "You are StudySpark, an expert study coach for students. "
    "You answer ONLY with valid JSON — no markdown, no code fences, no commentary. "
    "Study material must be clear, correct, and easy to memorize."
)


def _build_prompt(kind: str, notes: str) -> list[dict]:
    if kind == "flashcards":
        task = "Create 10 to 15 flashcards covering the most important facts."
    elif kind == "quiz":
        task = "Create 6 to 10 multiple-choice questions with 4 options each."
    else:
        task = "Write a clear summary with key points and a glossary of key terms."

    user_msg = (
        f"Task: {task}\n"
        f"Return ONLY JSON matching exactly this schema:\n{_SCHEMAS[kind]}\n\n"
        f"Here are the student's notes:\n\"\"\"\n{notes}\n\"\"\""
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_msg},
    ]


# ---------------------------------------------------------------------------
# Provider calls (OpenAI-compatible APIs + Gemini)
# ---------------------------------------------------------------------------

def _call_openai_compatible(url: str, key: str, messages: list[dict]) -> str:
    model = AI_MODEL or DEFAULT_MODELS[AI_PROVIDER]
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.4,
            "response_format": {"type": "json_object"},  # forces valid JSON
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise AIError(f"AI provider error {resp.status_code}: {resp.text[:200]}")
    return resp.json()["choices"][0]["message"]["content"]


def _call_gemini(key: str, messages: list[dict]) -> str:
    model = AI_MODEL or DEFAULT_MODELS["gemini"]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    prompt = "\n\n".join(m["content"] for m in messages)
    resp = requests.post(
        url,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "response_mime_type": "application/json"},
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise AIError(f"Gemini error {resp.status_code}: {resp.text[:200]}")
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _parse_json(raw: str) -> dict:
    """Parse AI output as JSON, tolerating stray code fences."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: grab the outermost {...} block
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise AIError("The AI did not return valid JSON. Try again.")


# ---------------------------------------------------------------------------
# Validation — never trust AI output blindly!
# ---------------------------------------------------------------------------

def _validate(kind: str, data: dict) -> dict:
    if kind == "flashcards":
        cards = [
            {"front": str(c.get("front", "")).strip(), "back": str(c.get("back", "")).strip()}
            for c in data.get("flashcards", [])
            if c.get("front") and c.get("back")
        ]
        if len(cards) < 3:
            raise AIError("Not enough flashcards were generated. Add more detailed notes.")
        return {"flashcards": cards[:20]}

    if kind == "quiz":
        questions = []
        for q in data.get("questions", []):
            options = [str(o) for o in q.get("options", []) if o][:4]
            if len(options) < 3 or not q.get("question"):
                continue
            idx = q.get("answer_index", 0)
            if not isinstance(idx, int) or not (0 <= idx < len(options)):
                idx = 0
            questions.append({
                "question": str(q["question"]).strip(),
                "options": options,
                "answer_index": idx,
                "explanation": str(q.get("explanation", "")).strip(),
            })
        if len(questions) < 3:
            raise AIError("Not enough quiz questions were generated. Add more detailed notes.")
        return {"questions": questions[:15]}

    # summary
    overview = str(data.get("overview", "")).strip()
    key_points = [str(p).strip() for p in data.get("key_points", []) if p][:10]
    key_terms = [
        {"term": str(t.get("term", "")).strip(), "definition": str(t.get("definition", "")).strip()}
        for t in data.get("key_terms", [])
        if t.get("term") and t.get("definition")
    ][:10]
    if not overview and not key_points:
        raise AIError("Could not produce a summary. Add more detailed notes.")
    return {"overview": overview, "key_points": key_points, "key_terms": key_terms}


# ---------------------------------------------------------------------------
# DEMO MODE — offline generator (no API key needed!)
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "about", "after", "again", "also", "because", "before", "being", "between",
    "could", "every", "first", "found", "great", "however", "important", "known",
    "large", "many", "more", "most", "much", "often", "only", "other", "over",
    "people", "same", "should", "since", "some", "such", "than", "that", "their",
    "them", "then", "there", "these", "they", "this", "those", "through", "under",
    "very", "were", "what", "when", "where", "which", "while", "will", "with",
    "would", "your", "have", "from", "been", "were", "each", "into", "used",
}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text.strip()))
    return [p.strip() for p in parts if len(p.split()) >= 5]


def _top_terms(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z]{5,}", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w.capitalize() for w, _ in ranked[:limit]]


def _demo_generate(kind: str, notes: str) -> dict:
    sents = _sentences(notes)
    terms = _top_terms(notes)
    rng = random.Random(notes[:200])  # same notes -> same result (nice for testing)

    if kind == "flashcards":
        cards = []
        for s in sents:
            m = re.match(r"^(.*?)\s+(is|are|was|were|means)\s+(.*)$", s, flags=re.IGNORECASE)
            if m and 2 <= len(m.group(1).split()) <= 8:
                cards.append({"front": f"What {m.group(2)} {m.group(1)}?", "back": m.group(3)})
        used = {c["back"] for c in cards}
        for s in sents:
            if len(cards) >= 12:
                break
            if s in used:
                continue
            snippet = " ".join(s.split()[:9]) + "…"
            cards.append({"front": f"Explain: “{snippet}”", "back": s})
        return {"flashcards": cards}

    if kind == "quiz":
        questions = []
        for term in terms:
            for s in sents:
                if term.lower() in s.lower():
                    distractors = [t for t in terms if t != term]
                    rng.shuffle(distractors)
                    options = ([term] + distractors)[:4]
                    rng.shuffle(options)
                    questions.append({
                        "question": re.sub(re.escape(term), "_____", s, count=1, flags=re.IGNORECASE),
                        "options": options,
                        "answer_index": options.index(term),
                        "explanation": f"The notes say: “{s}”",
                    })
                    break
        return {"questions": questions[:8]}

    # summary
    overview = " ".join(sents[:2]) if sents else notes[:300]
    key_points = sents[2:8] if len(sents) > 2 else sents
    key_terms = []
    for term in terms[:6]:
        definition = next((s for s in sents if term.lower() in s.lower()), "")
        key_terms.append({"term": term, "definition": definition[:200] or "See your notes."})
    return {"overview": overview, "key_points": key_points, "key_terms": key_terms}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_study_material(kind: str, notes: str) -> dict:
    """Generate study material of the given kind from raw notes. Returns the validated dict."""
    if kind not in _SCHEMAS:
        raise AIError(f"Unknown study set kind: {kind}")

    notes = notes.strip()
    if len(notes) > MAX_NOTES_LENGTH:
        notes = notes[:MAX_NOTES_LENGTH]

    if is_demo_mode():
        return _validate(kind, _demo_generate(kind, notes))

    messages = _build_prompt(kind, notes)
    try:
        if AI_PROVIDER == "groq":
            raw = _call_openai_compatible(
                "https://api.groq.com/openai/v1/chat/completions", _get_key(), messages
            )
        elif AI_PROVIDER == "openai":
            raw = _call_openai_compatible(
                "https://api.openai.com/v1/chat/completions", _get_key(), messages
            )
        elif AI_PROVIDER == "gemini":
            raw = _call_gemini(_get_key(), messages)
        else:
            raise AIError(f"Unknown AI_PROVIDER: {AI_PROVIDER}")
    except requests.RequestException as exc:
        raise AIError(f"Could not reach the AI service: {exc}") from exc

    return _validate(kind, _parse_json(raw))
