"""Advisor and sources (SPEC §16, private): questions answered by the local model from your own sources only.

Sources are growing guides, seed packets, papers and notes you add on /sources. A question on /advisor is answered
by the local model through the agent gateway (``LLM_BASE_URL``, model ``LLM_MODEL``), given only the best matching
sources, numbered. The answer must cite them as [1], [2] …; an answer without a valid citation is rejected and
shown as "not in the sources". The prompt, the model call and the citation check are human-owned (glue at the
bottom). The loop fills in the source search and the source form, marked ``TODO (task Axx)``.
"""

# ruff: noqa: E501  (step docstrings are long on purpose)

import asyncio
import json
import re
import urllib.request
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequireUser
from app.config import Settings
from app.db import SessionLocal
from app.models import SOURCE_KINDS, Source
from app.templating import render

router = APIRouter()

WORD = re.compile(r"[a-z0-9à-ÿ]+")
STOPWORDS = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "what",
        "when",
        "how",
        "does",
        "can",
        "should",
        "this",
        "that",
        "from",
        "are",
        "was",
        "were",
        "have",
        "has",
        "into",
        "your",
        "you",
        "about",
        "which",
        "there",
        "their",
        "them",
        "then",
        "than",
        "its",
        "also",
        "not",
        "but",
        "all",
        "any",
        "too",
        "very",
        "wat",
        "hoe",
        "wanneer",
        "welke",
        "een",
        "het",
        "van",
        "voor",
        "met",
        "zijn",
        "kan",
        "moet",
        "ook",
        "niet",
        "maar",
        "als",
        "bij",
        "naar",
    ]
)
FORM_FIELDS = ("title", "kind", "url", "publisher", "body", "tags")


def tokenize(text: str) -> list[str]:
    """Search words in *text*: lower case, letters and digits only, at least 3 long, no stopwords. Keeps repeats.

    TODO (task A10): ``[w for w in WORD.findall(text.lower()) if len(w) >= 3 and w not in STOPWORDS]``.
    """
    return [w for w in WORD.findall(text.lower()) if len(w) >= 3 and w not in STOPWORDS]


def rank_sources(sources: list[Source], question: str, k: int = 4) -> list[Source]:
    """The *k* sources that best match *question*.

    TODO (task A11) steps:
    1. ``terms = set(tokenize(question))``; no terms → ``[]``.
    2. For each source: ``title = tokenize(s.title)``, ``tags = tokenize(s.tags)``, ``body = tokenize(s.body)``;
       ``score = sum(3 * title.count(t) + 2 * tags.count(t) + body.count(t) for t in terms)``.
    3. Drop sources with score 0. Sort by score (highest first), then ``s.id`` (lowest first); return the first *k*.
    """
    terms = set(tokenize(question))
    if not terms:
        return []
    scored: list[tuple[int, int]] = []
    for s in sources:
        title = tokenize(s.title)
        tags = tokenize(s.tags)
        body = tokenize(s.body)
        score = sum(3 * title.count(t) + 2 * tags.count(t) + body.count(t) for t in terms)
        if score > 0:
            scored.append((score, s.id))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s for _, sid in scored[:k] for s in sources if s.id == sid]


def snippet(body: str, terms: set[str], width: int = 600) -> str:
    """The part of *body* (at most *width* characters) around the first search term, for the prompt.

    TODO (task A12) steps:
    1. ``low = body.lower()``; ``hits = [low.find(t) for t in terms if low.find(t) >= 0]``.
    2. No hits, or ``len(body) <= width`` → ``body[:width]``.
    3. ``start = max(0, min(hits) - width // 4)``; ``part = body[start:start + width]``.
    4. Add "…" in front when ``start > 0`` and at the end when ``start + width < len(body)``; return it.
    """
    return body[:width]


def validate_source(form: dict[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
    """Check the source form; ``(values, errors)`` with every key of FORM_FIELDS in *values*.

    TODO (task A13) steps, ``get = lambda k: (form.get(k) or "").strip()``:
    1. title: 1–200 characters, else "Give it a title (at most 200 characters)".
    2. kind not in SOURCE_KINDS → "Pick a kind".
    3. url: "" → None; must start with "http://" or "https://" and be at most 500 long, else
       "Use a full link (https://…)" (keep the text).
    4. publisher: "" → None; at most 120, else "At most 120 characters".
    5. body: 1–20000 characters, else "Paste the text the advisor may use (at most 20000 characters)".
    6. tags: split on ",", strip, lower case, drop empty ones, join with ", "; longer than 200 → "At most 200 characters".
    """
    return {}, {}


# -- glue (done)
SYSTEM = (
    "You answer questions about a vegetable garden (an allotment in the Netherlands). Use ONLY the numbered "
    "sources below. Cite every claim with the source number in square brackets, like [1] or [2]. If the sources "
    "do not answer the question, reply exactly: NOT IN SOURCES. Do not use outside knowledge. Answer in the "
    "language of the question, in at most 150 words."
)
NOT_FOUND = "NOT IN SOURCES"
CITE = re.compile(r"\[(\d+)\]")


def build_messages(question: str, picked: list[Source]) -> list[dict[str, str]]:
    terms = set(tokenize(question))
    blocks = [
        f"[{i}] {s.title}"
        + (f" ({s.publisher})" if s.publisher else "")
        + f"\n{snippet(s.body, terms)}"
        for i, s in enumerate(picked, 1)
    ]
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}",
        },
    ]


def check_citations(answer: str, n: int) -> list[int] | None:
    """The cited source numbers when the answer is usable, else None (no citation, a bad number, or NOT IN SOURCES)."""
    if NOT_FOUND in answer.upper():
        return None
    cited = sorted({int(x) for x in CITE.findall(answer)})
    if not cited or any(c < 1 or c > n for c in cited):
        return None
    return cited


def ask_llm(messages: list[dict[str, str]]) -> str:
    """One chat completion through the gateway (OpenAI-compatible). Raises on any failure."""
    s = Settings()
    req = urllib.request.Request(
        s.LLM_BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(
            {"model": s.LLM_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 600}
        ).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {s.LLM_API_KEY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310: URL comes from our own settings
        data = json.loads(r.read())
    return str(data["choices"][0]["message"]["content"]).strip()


def _sources(db: Session) -> list[Source]:
    return list(db.execute(select(Source).order_by(Source.title)).scalars())


@router.get("/advisor")
async def advisor_page(request: Request, user: str = RequireUser) -> HTMLResponse:
    db = SessionLocal()
    try:
        n = len(_sources(db))
    finally:
        db.close()
    return render(
        request,
        "advisor.html",
        active="growth",
        question="",
        result=None,
        n_sources=n,
        enabled=bool(Settings().LLM_BASE_URL),
    )


@router.post("/advisor")
async def advisor_ask(request: Request, user: str = RequireUser) -> HTMLResponse:
    question = str((await request.form()).get("question") or "").strip()[:500]
    enabled = bool(Settings().LLM_BASE_URL)
    db = SessionLocal()
    try:
        all_sources = _sources(db)
    finally:
        db.close()
    picked = rank_sources(all_sources, question)
    result: dict[str, Any] = {"state": "none", "picked": picked}
    if not question:
        result["state"] = "empty"
    elif not enabled:
        result["state"] = "off"
    elif picked:
        try:
            answer = await asyncio.to_thread(ask_llm, build_messages(question, picked))
        except Exception:  # noqa: BLE001  (gateway down, PC asleep, bad reply: say so, don't crash)
            result["state"] = "error"
        else:
            cited = check_citations(answer, len(picked))
            if cited:
                result.update(state="ok", answer=answer, cited=[(i, picked[i - 1]) for i in cited])
    return render(
        request,
        "advisor.html",
        active="growth",
        question=question,
        result=result,
        n_sources=len(all_sources),
        enabled=enabled,
    )


def _get(db: Session, source_id: int) -> Source:
    s = db.get(Source, source_id)
    if s is None:
        raise HTTPException(status_code=404, detail="No such source")
    return s


def _form_page(
    request: Request, src: Source | None, values: dict[str, Any], errors: dict[str, str]
) -> HTMLResponse:
    return render(
        request,
        "source_form.html",
        status_code=400 if errors else 200,
        active="growth",
        source=src,
        values=values,
        errors=errors,
        kinds=[(k, k.replace("_", " ").title()) for k in SOURCE_KINDS],
    )


@router.get("/sources")
async def sources_page(request: Request, user: str = RequireUser) -> HTMLResponse:
    db = SessionLocal()
    try:
        rows = _sources(db)
    finally:
        db.close()
    return render(request, "sources.html", active="growth", sources=rows)


@router.get("/sources/new")
async def source_new(request: Request, user: str = RequireUser) -> HTMLResponse:
    return _form_page(request, None, {"kind": "guide"}, {})


@router.get("/sources/{source_id}/edit")
async def source_edit(request: Request, source_id: int, user: str = RequireUser) -> HTMLResponse:
    db = SessionLocal()
    try:
        src = _get(db, source_id)
        return _form_page(request, src, {k: getattr(src, k) for k in FORM_FIELDS}, {})
    finally:
        db.close()


async def _save(request: Request, source_id: int | None) -> HTMLResponse | RedirectResponse:
    form = {k: str(v) for k, v in (await request.form()).items()}
    db = SessionLocal()
    try:
        src = _get(db, source_id) if source_id is not None else None
        values, errors = validate_source(form)
        if errors:
            return _form_page(request, src, values, errors)
        if src is None:
            src = Source()
            db.add(src)
        for k in FORM_FIELDS:
            setattr(src, k, values[k])
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/sources", status_code=303)


@router.post("/sources", response_model=None)
async def source_create(
    request: Request, user: str = RequireUser
) -> HTMLResponse | RedirectResponse:
    return await _save(request, None)


@router.post("/sources/{source_id}", response_model=None)
async def source_update(
    request: Request, source_id: int, user: str = RequireUser
) -> HTMLResponse | RedirectResponse:
    return await _save(request, source_id)


@router.post("/sources/{source_id}/delete")
async def source_delete(source_id: int, user: str = RequireUser) -> RedirectResponse:
    db = SessionLocal()
    try:
        db.delete(_get(db, source_id))
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/sources", status_code=303)
