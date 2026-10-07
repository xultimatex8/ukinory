from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

from django.conf import settings
from google import genai
from google.genai import types

from apps.common import api_quota
from apps.recommendations.services.joint_profile import JointCandidate
from apps.comparisons.dtos.narrative_result import NarrativeResult

logger = logging.getLogger(__name__)

QUOTA_CLIENT_NAME = "gemini_generate"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_MAX_OUTPUT_TOKENS = 400
MAX_DESCRIPTION_CHARS = 400


def _labels(user_ids: Sequence[str]) -> dict[str, str]:
    return {uid: f"User {chr(65 + i)}" for i, uid in enumerate(user_ids)}


def _anonymise(public: dict, labels: dict[str, str]) -> dict:
    out = dict(public)
    out["library_sizes"] = {
        labels[k]: v for k, v in public["library_sizes"].items()
    }
    for key in ("agreements", "divergences"):
        out[key] = [
            {**e, "ratings": {labels[k]: v for k, v in e["ratings"].items()}}
            for e in public[key]
        ]
    return out


def _build_prompt(
    public: dict,
    internal: dict,
    candidates: Sequence[JointCandidate],
    user_ids: Sequence[str],
) -> str:
    labels = _labels(user_ids)
    lines = []
    for i, c in enumerate(candidates, 1):
        m = c.movie
        genres = ", ".join(g.name for g in m.genres.all())
        fit = ", ".join(
            f"{labels[uid]}={s:.2f}" for uid, s in zip(user_ids, c.per_user)
        )
        desc = (m.wikidata_description or "")[:MAX_DESCRIPTION_CHARS]
        lines.append(
            f"{i}. {m.title} ({m.release_year}) | genres: {genres} | "
            f"taste fit: {fit}\n   {desc}"
        )
    candidates_block = "\n".join(lines) or "(none)"

    return (
        "You are a movie taste-compatibility assistant for two people. "
        "Using ONLY the data below, do two things:\n"
        "1. Write a short narrative (3-5 sentences) about how their tastes "
        "overlap and diverge. Address both of them together in the second "
        "person plural. Do not just list numbers.\n"
        "2. For each candidate movie, write ONE sentence explaining why it "
        "suits both of them, grounded in the shared data.\n"
        "Do not invent films, ratings or facts not present in the data. "
        "Refer to people as 'User A' / 'User B' only if needed.\n"
        'Respond ONLY with JSON: {"narrative": str, "recommendations": '
        '[{"index": int, "reason": str}]}\n\n'
        f"Compatibility metrics:\n{json.dumps(_anonymise(public, labels), ensure_ascii=False)}\n\n"
        f"Shared favourite genres: {', '.join(internal.get('shared_genres', [])) or 'none'}\n"
        f"Shared favourite directors: {', '.join(internal.get('shared_directors', [])) or 'none'}\n\n"
        f"Candidate movies (neither has watched them):\n{candidates_block}"
    )


def _parse(text: str, n_candidates: int) -> Optional[NarrativeResult]:
    try:
        data = json.loads(text)
        summary = str(data["narrative"]).strip()
        reasons: dict[int, str] = {}
        for item in data.get("recommendations", []):
            idx = int(item["index"])
            if 1 <= idx <= n_candidates:
                reasons[idx] = str(item["reason"]).strip()
    except (ValueError, KeyError, TypeError):
        return None
    return NarrativeResult(summary=summary, reasons=reasons) if summary else None


@dataclass(slots=True)
class ComparisonNarrativeClient:
    api_key: Optional[str] = None
    model: str = DEFAULT_MODEL
    _client: genai.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key or getattr(settings, "GEMINI_API_KEY", None)
        self._client = genai.Client(api_key=self.api_key)

    def generate(
        self,
        *,
        public: dict,
        internal: dict,
        candidates: Sequence[JointCandidate],
        user_ids: Sequence[str],
    ) -> Optional[NarrativeResult]:
        prompt = _build_prompt(public, internal, candidates, user_ids)

        reserved = api_quota.cost_units(
            QUOTA_CLIENT_NAME,
            input_tokens=api_quota.estimate_tokens(prompt),
            output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        )
        try:
            api_quota.consume(QUOTA_CLIENT_NAME, reserved)
        except api_quota.QuotaExceeded as exc:
            logger.warning("Skipping comparison narrative: %s", exc)
            return None

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
                ),
            )
            self._reconcile_cost(response, reserved)
            parsed = _parse(response.text or "", len(candidates))
            if parsed is None:
                logger.warning("Unparseable comparison narrative response")
            return parsed
        except Exception as exc:
            logger.warning("Could not generate comparison narrative: %s", exc)
            return None

    @staticmethod
    def _reconcile_cost(response, reserved: int) -> None:
        usage = getattr(response, "usage_metadata", None)
        if usage is None or usage.prompt_token_count is None:
            return
        actual = api_quota.cost_units(
            QUOTA_CLIENT_NAME,
            input_tokens=usage.prompt_token_count or 0,
            output_tokens=(usage.candidates_token_count or 0)
            + (usage.thoughts_token_count or 0),
        )
        api_quota.adjust(QUOTA_CLIENT_NAME, actual - reserved)
