"""LLM-backed personalized cold-email generation.

The output schema is enforced by asking the model to return JSON with
``subject`` and ``body`` keys. We parse defensively because local models
sometimes wrap JSON in code fences or chatter.

Supported providers (``LLM_PROVIDER`` env var or ``--provider`` CLI flag):
  google    — Gemini via its OpenAI-compatible endpoint (default)
  lmstudio  — Local LM Studio instance
"""
from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from openai import OpenAI

from auto_marketer.security import sanitize_for_prompt

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, dict[str, str]] = {
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-pro",
    },
    "lmstudio": {
        "base_url": os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
        "api_key_env": "LM_STUDIO_API_KEY",
        "default_model": os.getenv("CHAT_MODEL_NAME", "local-model"),
    },
}

DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "google")

DEFAULT_GOAL = (
    "Offer elite offshore product development teams and Virtual Assistants "
    "to help SMBs scale without high overhead."
)

_SYSTEM_PROMPT = (
    "You are an expert B2B sales development representative. "
    "You write concise, highly personalized cold emails. "
    "You ALWAYS reply with valid JSON in the exact form "
    '{"subject": "...", "body": "..."}. No prose, no markdown, no code fences.'
)


def _build_client(provider: str = DEFAULT_PROVIDER) -> OpenAI:
    cfg = _PROVIDERS.get(provider)
    if cfg is None:
        raise ValueError(f"Unknown LLM provider {provider!r}. Choose from: {list(_PROVIDERS)}")
    api_key = os.getenv(cfg["api_key_env"], "")
    if not api_key:
        raise ValueError(f"Provider {provider!r} requires env var {cfg['api_key_env']} to be set")
    return OpenAI(base_url=cfg["base_url"], api_key=api_key)


def _default_model(provider: str = DEFAULT_PROVIDER) -> str:
    return _PROVIDERS.get(provider, _PROVIDERS["google"])["default_model"]


def _extract_company(profile: dict) -> str:
    if profile.get("company"):
        return str(profile["company"])
    raw = profile.get("raw_data") or {}
    if isinstance(raw, dict):
        positions = raw.get("currentPosition") or []
        if positions and isinstance(positions[0], dict):
            name = positions[0].get("companyName")
            if name:
                return str(name)
    return "your company"


def _extract_recipient_email(profile: dict) -> str | None:
    if profile.get("recipient_email"):
        return str(profile["recipient_email"])
    if profile.get("email"):
        return str(profile["email"])
    raw = profile.get("raw_data") or {}
    if isinstance(raw, dict):
        emails = raw.get("emails") or []
        if emails:
            first = emails[0]
            if isinstance(first, dict):
                return first.get("email")
            return str(first)
    return None


def _parse_llm_json(text: str) -> dict[str, str]:
    text = text.strip()
    # Strip ```json fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Find first {...} block.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("LLM output contained no JSON object")
    payload = json.loads(match.group(0))
    subject = str(payload.get("subject", "")).strip()
    body = str(payload.get("body", "")).strip()
    if not subject or not body:
        raise ValueError("LLM JSON missing subject or body")
    return {"subject": subject, "body": body}


def generate_email(
    profile: dict,
    *,
    tone: str = "professional",
    goal: str = DEFAULT_GOAL,
    model: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    client: OpenAI | None = None,
) -> dict[str, str]:
    """Generate a single personalized email for ``profile``.

    Returns ``{"subject": ..., "body": ...}``. Raises ``ValueError`` if the
    LLM output cannot be parsed.
    """
    first = profile.get("first_name") or ""
    last = profile.get("last_name") or ""
    name = f"{first} {last}".strip() or "there"
    company = _extract_company(profile)
    research = profile.get("research_summary") or profile.get("summary") or ""

    # All untrusted text is wrapped in fenced markers so the model treats
    # it as data, not instructions.
    safe_research = sanitize_for_prompt(research, label="research")
    safe_name = sanitize_for_prompt(name, label="name")
    safe_company = sanitize_for_prompt(company, label="company")
    safe_goal = sanitize_for_prompt(goal, label="goal")
    safe_tone = sanitize_for_prompt(tone, label="tone")

    user_prompt = (
        "Write one personalized cold email.\n\n"
        f"Prospect name:\n{safe_name}\n\n"
        f"Company:\n{safe_company}\n\n"
        f"Research context:\n{safe_research}\n\n"
        f"Tone:\n{safe_tone}\n\n"
        f"Goal of the email:\n{safe_goal}\n\n"
        'Reply with JSON: {"subject": "...", "body": "..."}'
    )

    client = client or _build_client(provider)
    response = client.chat.completions.create(
        model=model or _default_model(provider),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    raw = response.choices[0].message.content or ""
    parsed = _parse_llm_json(raw)
    return parsed


def generate_batch(
    profiles: list[dict],
    *,
    workers: int = 3,
    tone: str = "professional",
    goal: str = DEFAULT_GOAL,
    model: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    client: OpenAI | None = None,
) -> list[dict[str, Any]]:
    """Generate emails for many profiles in parallel.

    Returns a list aligned with ``profiles`` containing
    ``{"profile": p, "ok": bool, "subject", "body", "recipient_email", "recipient_name", "error"}``.
    """
    results: list[dict[str, Any] | None] = [None] * len(profiles)

    def _one(idx: int, prof: dict) -> tuple[int, dict[str, Any]]:
        try:
            email = generate_email(
                prof, tone=tone, goal=goal, model=model, provider=provider, client=client
            )
            return idx, {
                "profile": prof,
                "ok": True,
                "subject": email["subject"],
                "body": email["body"],
                "recipient_email": _extract_recipient_email(prof),
                "recipient_name": f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip(),
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 — collected per-row, not raised
            log.warning("generate_email failed for profile %s: %s", prof.get("id"), exc)
            return idx, {
                "profile": prof,
                "ok": False,
                "subject": None,
                "body": None,
                "recipient_email": _extract_recipient_email(prof),
                "recipient_name": f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip(),
                "error": str(exc),
            }

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [ex.submit(_one, i, p) for i, p in enumerate(profiles)]
        for f in as_completed(futs):
            idx, payload = f.result()
            results[idx] = payload

    return [r for r in results if r is not None]
