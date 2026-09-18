"""Thin LLM client.

Deliberately narrow: the scheduling and allocation engines never call this. The
AI layer only turns already-computed, already-explained decisions into prose.
Any failure (no key, quota exhausted, timeout, provider outage) degrades to
``None`` and the caller falls back to the deterministic explanation.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a production planning assistant for a design-and-build joinery company. "
    "You are given allocation decisions that were already made by a deterministic "
    "scheduling engine. Never invent dates, names or numbers, and never contradict "
    "the facts you are given. Reply with one short, factual sentence per item, in "
    "plain business English, no bullet points and no preamble."
)


class AIUnavailable(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.ai_enabled and settings.ai_api_key)


def complete(prompt: str, *, max_tokens: int = 600, temperature: float = 0.2) -> str:
    """One chat completion. Raises AIUnavailable on any problem."""
    if not is_configured():
        raise AIUnavailable("AI layer disabled or no API key configured")

    try:
        response = httpx.post(
            f"{settings.ai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.ai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.ai_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=settings.ai_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        log.warning("AI provider call failed: %s", exc)
        raise AIUnavailable(str(exc)) from exc

    if not content or not content.strip():
        raise AIUnavailable("empty completion")
    return content.strip()
