from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings
from google import genai
from google.genai import types

from apps.common import api_quota
from apps.common.exceptions import AIUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.1-flash-lite"



@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    finish_reason: Any = None


class GeminiClient:
    quota_name: str = ""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", None)
        self.model = model or DEFAULT_MODEL
        self._client = genai.Client(api_key=self.api_key)

    def complete(
        self,
        prompt: str,
        *,
        max_output_tokens: int,
        json_output: bool = False,
        label: str = "",
    ) -> Completion:
        if not self.quota_name:
            raise NotImplementedError("GeminiClient subclasses must set quota_name")
        label = label or self.quota_name

        reserved = api_quota.cost_units(
            self.quota_name,
            input_tokens=api_quota.estimate_tokens(prompt),
            output_tokens=max_output_tokens,
        )
        try:
            api_quota.consume(self.quota_name, reserved)
        except api_quota.QuotaExceeded as exc:
            logger.warning("Skipping %s: %s", label, exc)
            raise AIUnavailableError from exc

        config_kwargs = {"response_mime_type": "application/json"} if json_output else {}
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
                    **config_kwargs,
                ),
            )
            text = (response.text or "").strip()
        except Exception as exc:
            logger.warning("Could not generate %s with model %s: %s", label, self.model, exc)
            raise AIUnavailableError from exc

        self._reconcile_cost(response, reserved, label)

        finish_reason = _finish_reason(response)
        if not text:
            logger.warning(
                "Empty Gemini response for %s (finish_reason=%s)", label, finish_reason
            )
            raise AIUnavailableError("empty response")
        return Completion(text=text, finish_reason=finish_reason)

    def _reconcile_cost(self, response, reserved: int, label: str) -> None:
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage is None or usage.prompt_token_count is None:
                return
            actual = api_quota.cost_units(
                self.quota_name,
                input_tokens=usage.prompt_token_count or 0,
                output_tokens=(usage.candidates_token_count or 0)
                + (usage.thoughts_token_count or 0),
            )
            logger.info(
                "%s usage: in=%s out=%s thoughts=%s units=%s reserved=%s",
                label,
                usage.prompt_token_count,
                usage.candidates_token_count,
                usage.thoughts_token_count,
                actual,
                reserved,
            )
            api_quota.adjust(self.quota_name, actual - reserved)
        except Exception as exc:
            logger.warning("Could not reconcile quota cost for %s: %s", label, exc)


def _finish_reason(response) -> Any:
    candidates = getattr(response, "candidates", None) or [None]
    return getattr(candidates[0], "finish_reason", None)
