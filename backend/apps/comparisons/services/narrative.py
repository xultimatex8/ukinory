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

QUOTA_CLIENT_NAME = "gemini_narrative"
DEFAULT_MODEL = "gemini-3.1-flash-lite"

DEFAULT_MAX_OUTPUT_TOKENS = 600
MAX_DESCRIPTION_CHARS = 160


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _shorten(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0]


def _letters(user_ids: Sequence[str]) -> list[str]:
    return [chr(65 + i) for i in range(len(user_ids))]


def _labels(user_ids: Sequence[str]) -> dict[str, str]:
    return dict(zip(user_ids, _letters(user_ids)))


def _compact_public(public: dict, labels: dict[str, str]) -> dict:
    def entry(e: dict) -> dict:
        return {
            "title": e["title"],
            "year": e.get("release_year"),
            "ratings": {labels[k]: v for k, v in e["ratings"].items()},
        }

    return {
        "compatibility_score": public.get("compatibility_score"),
        "taste_similarity": public.get("taste_similarity"),
        "common_films": public.get("common_count"),
        "mean_rating_gap": public.get("mean_rating_gap"),
        "rating_correlation": public.get("rating_correlation"),
        "library_sizes": {
            labels[k]: v for k, v in public["library_sizes"].items()
        },
        "agreements": [entry(e) for e in public["agreements"]],
        "divergences": [entry(e) for e in public["divergences"]],
    }


def _profiles_block(internal: dict, labels: dict[str, str]) -> str:
    profiles = internal.get("profiles") or {}
    lines = [
        f"{labels[uid]}: {_json(profile)}"
        for uid, profile in profiles.items()
        if uid in labels
    ]
    return "\n".join(lines) or "(none)"


def _build_prompt(
    public: dict,
    internal: dict,
    candidates: Sequence[JointCandidate],
    user_ids: Sequence[str],
) -> str:
    labels = _labels(user_ids)
    letters = _letters(user_ids)

    lines = []
    for i, c in enumerate(candidates, 1):
        m = c.movie
        genres = ", ".join(g.name for g in m.genres.all())
        fit = " ".join(
            f"{labels[uid]}={s:.2f}" for uid, s in zip(user_ids, c.per_user)
        )
        desc = _shorten(m.wikidata_description, MAX_DESCRIPTION_CHARS)
        lines.append(
            f"{i}. {m.title} ({m.release_year}) | {genres} | fit {fit} | {desc}"
        )
    candidates_block = "\n".join(lines) or "(none)"

    individual_schema = ", ".join(f'"{letter}": str' for letter in letters)
    schema = (
        '{"narrative": str, "individual": {' + individual_schema + "}, "
        '"recommendations": [str, ...]}'
    )
    if candidates:
        recs_rule = (
            f"- recommendations: exactly {len(candidates)} strings, in the "
            "order of the candidates; each is ONE sentence (max 15 words) "
            "on why that movie suits both.\n"
        )
    else:
        recs_rule = "- recommendations: an empty list.\n"

    return (
        "You compare the movie taste of two people, A and B. Use ONLY the "
        "data below; never invent films, ratings or facts. Be concise.\n"
        f"Return minified JSON only: {schema}\n"
        "- narrative: 2-3 sentences (max 60 words) on how your tastes "
        "overlap and diverge, addressed to both of them (you both / one of "
        "you). Do not list numbers or use the labels A/B.\n"
        "- individual: for each person, 1-2 sentences (max 30 words) on "
        "their own taste: favourite genres and directors, how generously "
        "they rate, what sets them apart. Third person; never use names, "
        "the labels A/B or 'you', because both people see both profiles.\n"
        f"{recs_rule}\n"
        f"Metrics: {_json(_compact_public(public, labels))}\n\n"
        f"Individual taste data:\n{_profiles_block(internal, labels)}\n\n"
        f"Shared favourite genres: {', '.join(internal.get('shared_genres', [])) or 'none'}\n"
        f"Shared favourite directors: {', '.join(internal.get('shared_directors', [])) or 'none'}\n\n"
        f"Candidates (neither has watched them):\n{candidates_block}"
    )


def _parse(
    text: str, n_candidates: int, user_ids: Sequence[str]
) -> Optional[NarrativeResult]:
    try:
        data = json.loads(text)
        summary = str(data["narrative"]).strip()

        raw_individual = data["individual"]
        individual: dict[str, str] = {}
        for uid, letter in zip(user_ids, _letters(user_ids)):
            value = str(raw_individual[letter]).strip()
            if value:
                individual[uid] = value

        reasons: dict[int, str] = {}
        for pos, item in enumerate(data.get("recommendations", []), 1):
            if isinstance(item, dict):
                idx, reason = int(item.get("index", pos)), item["reason"]
            else:
                idx, reason = pos, item
            if 1 <= idx <= n_candidates:
                reasons[idx] = str(reason).strip()
    except (ValueError, KeyError, TypeError, AttributeError):
        return None

    if not summary or len(individual) != len(user_ids):
        return None
    return NarrativeResult(summary=summary, reasons=reasons, individual=individual)


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
            parsed = _parse(response.text or "", len(candidates), user_ids)
            if parsed is None:
                logger.warning(
                    "Unparseable comparison narrative response (finish_reason=%s)",
                    getattr(
                        (getattr(response, "candidates", None) or [None])[0],
                        "finish_reason",
                        None,
                    ),
                )
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
