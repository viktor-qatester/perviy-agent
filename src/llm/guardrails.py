"""Guardrails: only facts from events.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from src.llm.client import events_to_json
from src.llm.prompts import GUARDRAIL_SYSTEM

if TYPE_CHECKING:
    from src.llm.client import LLMClient
    from src.models import Event


@dataclass(frozen=True)
class GuardrailResult:
    safe: bool
    reason: str = ""


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip().rstrip(".,);"))
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc.lower()}{path}".lower()


def _known_urls(events: list[Event]) -> set[str]:
    urls: set[str] = set()
    for event in events:
        for raw in (event.url, event.source_url):
            if raw:
                urls.add(_normalize_url(raw))
    return urls


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\])>\"']+", text)


def check_urls_in_events(answer: str, events: list[Event]) -> GuardrailResult:
    """Reject answers that cite URLs not present in events."""
    known = _known_urls(events)
    for url in _extract_urls(answer):
        if _normalize_url(url) not in known:
            return GuardrailResult(
                safe=False,
                reason=f"URL not in events: {url}",
            )
    return GuardrailResult(safe=True)


def _parse_guardrail_json(raw: str) -> GuardrailResult:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return GuardrailResult(safe=False, reason="Guardrail returned invalid JSON")

    if not isinstance(data, dict) or "safe" not in data:
        return GuardrailResult(safe=False, reason="Guardrail JSON missing 'safe' field")

    if data["safe"] is True:
        return GuardrailResult(safe=True)

    reason = str(data.get("reason") or "LLM guardrail flagged hallucination")
    return GuardrailResult(safe=False, reason=reason)


def check_support_answer_llm(
    client: LLMClient,
    answer: str,
    events: list[Event],
) -> GuardrailResult:
    payload = json.dumps(
        {"answer": answer, "events": json.loads(events_to_json(events))},
        ensure_ascii=False,
        indent=2,
    )
    raw = client.complete(GUARDRAIL_SYSTEM, payload, temperature=0.0)
    return _parse_guardrail_json(raw)


def check_support_answer(
    client: LLMClient | None,
    answer: str,
    events: list[Event],
) -> GuardrailResult:
    """Programmatic URL check + optional LLM self-check."""
    url_check = check_urls_in_events(answer, events)
    if not url_check.safe:
        return url_check

    if client is None:
        return GuardrailResult(safe=True)

    return check_support_answer_llm(client, answer, events)
