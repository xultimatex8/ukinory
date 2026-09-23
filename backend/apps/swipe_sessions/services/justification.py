from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings
from google import genai
from google.genai import types

from apps.common import api_quota
from apps.library.models import Rating
from apps.movies.models import Movie
from apps.swipe_sessions.models import (
    CandidateJustification,
    SwipeSession,
    SwipeSessionCandidate,
)
from apps.swipe_sessions.exceptions import CandidateNotFoundError, JustificationUnavailableError, NotSessionMemberError, SwipeSessionNotFoundError
from apps.swipe_sessions.services.session import ensure_session_active

logger = logging.getLogger(__name__)

QUOTA_CLIENT_NAME = "gemini_generate"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_MAX_OUTPUT_TOKENS = 80
DEFAULT_MAX_HISTORY_MOVIES = 5


@dataclass(slots=True)
class JustificationClient:
    api_key: Optional[str] = None
    model: Optional[str] = DEFAULT_MODEL
    _client: genai.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key or getattr(settings, "GEMINI_API_KEY", None)
        self._client = genai.Client(api_key=self.api_key)

    def generate(self, user, movie: Movie) -> str:
        history = _recent_liked_ratings(user)
        prompt = _build_prompt(movie, history)

        reserved = api_quota.cost_units(
            QUOTA_CLIENT_NAME,
            input_tokens=api_quota.estimate_tokens(prompt),
            output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
        )
        try:
            api_quota.consume(QUOTA_CLIENT_NAME, reserved)
        except api_quota.QuotaExceeded as exc:
            logger.warning("Skipping justification for movie %s: %s", movie.pk, exc)
            raise JustificationUnavailableError from exc

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                    thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
                ),
            )
            self._reconcile_cost(response, reserved)
            return (response.text or "").strip()
        except Exception as exc:
            logger.warning(
                "Could not generate justification for movie %s with model %s: %s",
                movie.pk,
                self.model,
                exc,
            )

        return ""

    @staticmethod
    def _reconcile_cost(response, reserved: int) -> None:
        usage = getattr(response, "usage_metadata", None)
        if usage is None or usage.prompt_token_count is None:
            return
        actual = api_quota.cost_units(
            QUOTA_CLIENT_NAME,
            input_tokens=usage.prompt_token_count or 0,
            output_tokens=(usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0),
        )
        api_quota.adjust(QUOTA_CLIENT_NAME, actual - reserved)


def ensure_candidate_justification(
    candidate: SwipeSessionCandidate,
    user,
) -> CandidateJustification:
    justification = getattr(candidate, "justification", None)

    if justification is not None and justification.text:
        return justification

    client = JustificationClient()
    text = client.generate(user=user, movie=candidate.movie)

    justification, _ = CandidateJustification.objects.update_or_create(
        candidate=candidate,
        defaults={
            "text": text,
            "model_version": client.model,
        },
    )

    return justification


def get_candidate_justification(
    user,
    session_id,
    candidate_id,
) -> tuple[SwipeSessionCandidate, CandidateJustification]:
    try:
        session = SwipeSession.objects.get(pk=session_id)
    except SwipeSession.DoesNotExist as exc:
        raise SwipeSessionNotFoundError from exc

    if not session.users.filter(pk=user.pk).exists():
        raise NotSessionMemberError

    ensure_session_active(session)

    try:
        candidate = SwipeSessionCandidate.objects.get(
            pk=candidate_id,
            session=session,
        )
    except SwipeSessionCandidate.DoesNotExist as exc:
        raise CandidateNotFoundError from exc

    justification = ensure_candidate_justification(
        candidate=candidate,
        user=user,
    )

    return candidate, justification


def _recent_liked_ratings(user) -> list[Rating]:
    return list(
        Rating.objects.filter(user=user, rating__isnull=False)
        .order_by("-rating", "-watched_date")[:DEFAULT_MAX_HISTORY_MOVIES]
    )


def _build_prompt(movie: Movie, history: list[Rating]) -> str:
    history_lines = "\n".join(
        f"- {r.title} ({r.release_year}): {r.rating}/5" for r in history
    ) or "No rating history yet."

    return (
        "You are a movie recommendation assistant. In 1-2 sentences, explain "
        "why this movie might appeal to this user, referring specifically "
        "to some of their previous ratings. Do not invent any information "
        "that does not appear in the rating history. "
        f"Candidate movie: {movie.title} ({movie.release_year})\n"
        f"Synopsis/description: {movie.wikidata_description}\n"
        f"Genres: {', '.join(g.name for g in movie.genres.all())}\n\n"
        f"User's rating history:\n{history_lines}"
    )
