"""Cloud LLM client — DeepSeek by default (OpenAI-compatible API)."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import Settings


class LLMError(Exception):
    """LLM request failed."""


class LLMClient(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        """Return assistant text for system + user messages."""


class OpenAICompatibleClient(LLMClient):
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def complete(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            raise LLMError(str(exc)) from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMError("Empty response from LLM")
        return content.strip()


class GeminiClient(LLMClient):
    def __init__(self, *, api_key: str, model: str) -> None:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._model_name = model

    def complete(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        import google.generativeai as genai

        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system,
        )
        try:
            response = model.generate_content(
                user,
                generation_config={"temperature": temperature},
            )
        except Exception as exc:
            raise LLMError(str(exc)) from exc

        text = getattr(response, "text", None)
        if not text:
            raise LLMError("Empty response from Gemini")
        return text.strip()


def events_to_json(events: list) -> str:
    from src.models import Event, format_event_date

    payload = []
    for event in events:
        row = event.to_dict()
        row["display_date"] = format_event_date(event)
        payload.append(row)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def get_llm_client(settings: Settings) -> LLMClient | None:
    if not settings.llm_enabled:
        return None

    provider = settings.llm_provider.lower()

    if provider == "deepseek":
        if not settings.deepseek_api_key:
            return None
        return OpenAICompatibleClient(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            return None
        return OpenAICompatibleClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
        )

    if provider == "gemini":
        if not settings.gemini_api_key:
            return None
        return GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )

    return None
