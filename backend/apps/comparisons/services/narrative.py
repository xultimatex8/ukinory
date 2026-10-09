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

BASE_OUTPUT_TOKENS = 650
OUTPUT_TOKENS_PER_REC = 62
DEFAULT_MAX_OUTPUT_TOKENS = BASE_OUTPUT_TOKENS + OUTPUT_TOKENS_PER_REC * 10

MAX_DESCRIPTION_CHARS = 100
PROMPT_ENTRIES = 3
MAX_ANGLES = 3

STYLE_REFERENCE = (
    'narrative: "Alien and Amélie are where you two meet, but one of you '
    "hands out five stars like candy while the other treats a four as a "
    "rave. Your biggest fight is Blade Runner, a masterpiece or a nap "
    'depending on who you ask. Settle it with a double feature."\n'
    'individual: "Horror and sci-fi loyalist who keeps coming back to '
    "Carpenter. A famously tough grader: a four from them is practically "
    'a rave."\n'
    'recommendation: "Carpenter-style dread for one of you and a slow-burn '
    'romance for the other, so nobody loses the coin toss."'
)


def _max_output_tokens(n_candidates: int) -> int:
    return BASE_OUTPUT_TOKENS + OUTPUT_TOKENS_PER_REC * n_candidates


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
        "agreements": [entry(e) for e in public["agreements"][:PROMPT_ENTRIES]],
        "divergences": [entry(e) for e in public["divergences"][:PROMPT_ENTRIES]],
    }


def _profiles_block(internal: dict, labels: dict[str, str]) -> str:
    profiles = internal.get("profiles") or {}
    lines = [
        f"{labels[uid]}: {_json(profile)}"
        for uid, profile in profiles.items()
        if uid in labels
    ]
    return "\n".join(lines) or "(none)"


def _fmt_ratings(entry: dict, labels: dict[str, str]) -> str:
    return " vs ".join(
        f"{labels[uid]}={rating}"
        for uid, rating in entry["ratings"].items()
        if uid in labels
    )


def _story_angles(public: dict, internal: dict, labels: dict[str, str]) -> list[str]:
    angles: list[str] = []

    sim = public.get("taste_similarity")
    corr = public.get("rating_correlation")
    common = public.get("common_count") or 0
    sizes = list((public.get("library_sizes") or {}).values())
    divergences = public.get("divergences") or []
    agreements = public.get("agreements") or []
    profiles = internal.get("profiles") or {}
    shared_directors = internal.get("shared_directors") or []
    shared_genres = internal.get("shared_genres") or []

    if sim is not None and corr is not None and sim >= 0.6 and corr < 0.3:
        angles.append(
            "Similar taste on paper, but they score the same films very "
            "differently."
        )
    elif sim is not None and sim < 0.3:
        angles.append("Their tastes pull in clearly different directions.")

    if divergences:
        d = divergences[0]
        angles.append(f"Sharpest clash: {d['title']} ({_fmt_ratings(d, labels)}).")

    means = {
        uid: p.get("mean_rating")
        for uid, p in profiles.items()
        if uid in labels and p.get("mean_rating") is not None
    }
    if len(means) == 2:
        (u1, m1), (u2, m2) = means.items()
        if abs(m1 - m2) >= 0.7:
            generous, tough = (u1, u2) if m1 > m2 else (u2, u1)
            angles.append(
                f"Rating style gap: {labels[generous]} is far more generous "
                f"than {labels[tough]}."
            )

    if agreements:
        a = agreements[0]
        angles.append(
            f"Common ground: both rated {a['title']} very high "
            f"({_fmt_ratings(a, labels)})."
        )

    if shared_directors:
        angles.append(f"Shared favourite director: {shared_directors[0]}.")
    elif shared_genres:
        angles.append(f"Shared favourite genre: {shared_genres[0]}.")

    if common < 10:
        angles.append("They have rated very few of the same films.")
    if len(sizes) == 2 and min(sizes) > 0 and max(sizes) / min(sizes) >= 3:
        angles.append("One of them has rated far more films than the other.")

    return angles[:MAX_ANGLES] or [
        "No standout pattern: focus on their favourite films and genres."
    ]


def _candidate_line(
    i: int, c: JointCandidate, labels: dict[str, str], user_ids: Sequence[str]
) -> str:
    m = c.movie
    genres = ", ".join(g.name for g in m.genres.all())
    directors = ", ".join(
        [d for d in (m.directors or []) if isinstance(d, str)][:2]
    )
    fit = " ".join(
        f"{labels[uid]}={s:.2f}" for uid, s in zip(user_ids, c.per_user)
    )

    tilt = ""
    if len(c.per_user) == 2 and abs(c.per_user[0] - c.per_user[1]) >= 0.25:
        lean = user_ids[0] if c.per_user[0] > c.per_user[1] else user_ids[1]
        tilt = f" (leans {labels[lean]})"

    desc = _shorten(m.wikidata_description, MAX_DESCRIPTION_CHARS)
    parts = [f"{i}. {m.title} ({m.release_year})", genres]
    if directors:
        parts.append(f"dir. {directors}")
    parts.append(f"fit {fit}{tilt}")
    parts.append(desc)
    return " | ".join(p for p in parts if p)


def _build_prompt(
    public: dict,
    internal: dict,
    candidates: Sequence[JointCandidate],
    user_ids: Sequence[str],
) -> str:
    labels = _labels(user_ids)
    letters = _letters(user_ids)

    candidates_block = (
        "\n".join(
            _candidate_line(i, c, labels, user_ids)
            for i, c in enumerate(candidates, 1)
        )
        or "(none)"
    )

    angles_block = "\n".join(
        f"{n}. {a}"
        for n, a in enumerate(_story_angles(public, internal, labels), 1)
    )

    individual_schema = ", ".join(f'"{letter}": str' for letter in letters)
    schema = (
        '{"narrative": str, "individual": {' + individual_schema + "}, "
        '"recommendations": [str, ...]}'
    )
    if candidates:
        recs_rule = (
            f"- recommendations: exactly {len(candidates)} strings, in the "
            "order of the candidates; each is ONE sentence (max 25 words) "
            "tying the film to something concrete: a shared director or "
            "genre, a film they both loved, or the pull between them. "
            "Do not mention or repeat the recommended film's title. "
            "The recommendation must make sense without naming the film. "
            "If a candidate 'leans' toward one person, pitch it as a compromise. "
            "Never just 'great film'. No labels A/B; say 'one of you'.\n"
        )
    else:
        recs_rule = "- recommendations: an empty list.\n"

    return (
        "You are a witty friend who knows cinema, writing a short personal "
        "readout of two people's movie taste, A and B. Use ONLY the data "
        "below; never invent films, ratings, directors or facts.\n"
        f"Return minified JSON only: {schema}\n\n"
        "STYLE: specific, warm, a bit playful. Name real films, directors or "
        "genres from the data; a line that fits any pair of people is a "
        "failure. No filler. Avoid 'diverse', 'eclectic', 'cinephile', "
        "'journey', 'a mix of', 'shared passion'. Don't open with 'You both'.\n\n"
        "FIELDS\n"
        "- narrative: 2-3 sentences (max 100 words) to both of them (you two / "
        "one of you). Build it around story angle 1, plus at most one more. "
        "Name one or two films. End with a light tease, not a summary. No "
        "numbers, no labels A/B.\n"
        "- individual: per person, 1-2 sentences (max 50 words) with a "
        "distinct signature: favourite films or directors by name and rating "
        "style (tough, generous...). The two must not read alike. Third "
        "person; never names, the labels A/B or 'you', because both people "
        "see both profiles.\n"
        f"{recs_rule}\n"
        f"Story angles (labels are for your reading only):\n{angles_block}\n\n"
        f"Metrics: {_json(_compact_public(public, labels))}\n\n"
        f"Individual taste data:\n{_profiles_block(internal, labels)}\n\n"
        f"Shared favourite genres: {', '.join(internal.get('shared_genres', [])) or 'none'}\n"
        f"Shared favourite directors: {', '.join(internal.get('shared_directors', [])) or 'none'}\n\n"
        f"Candidates (neither has watched them):\n{candidates_block}\n\n"
        "Tone reference only (other people and films; do not reuse its "
        f"wording or content):\n{STYLE_REFERENCE}"
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
        max_output_tokens = _max_output_tokens(len(candidates))

        reserved = api_quota.cost_units(
            QUOTA_CLIENT_NAME,
            input_tokens=api_quota.estimate_tokens(prompt),
            output_tokens=max_output_tokens,
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
                    max_output_tokens=max_output_tokens,
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
        logger.info(
            "Comparison narrative usage: in=%s out=%s thoughts=%s "
            "units=%s reserved=%s",
            usage.prompt_token_count,
            usage.candidates_token_count,
            usage.thoughts_token_count,
            actual,
            reserved,
        )
        api_quota.adjust(QUOTA_CLIENT_NAME, actual - reserved)
