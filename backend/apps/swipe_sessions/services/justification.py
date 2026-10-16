from __future__ import annotations

from django.db import transaction

from apps.common.enums import SwipeSessionType
from apps.common.services.gemini import AIUnavailableError, GeminiClient
from apps.library.models import Rating
from apps.movies.models import Movie
from apps.swipe_sessions.models import (
    CandidateJustification,
    SwipeSessionCandidate,
)
from apps.swipe_sessions.exceptions import CandidateNotFoundError, JustificationUnavailableError
from apps.swipe_sessions.services.session import (
    ensure_session_active,
    get_user_swipe_session,
)

QUOTA_CLIENT_NAME = "gemini_generate"
DEFAULT_MAX_OUTPUT_TOKENS = 80
DEFAULT_MAX_HISTORY_MOVIES = 35

JOINT_MAX_OUTPUT_TOKENS = 120
JOINT_MAX_HISTORY_MOVIES = 20


class JustificationClient(GeminiClient):
    quota_name = QUOTA_CLIENT_NAME

    def generate(self, user, movie: Movie) -> str:
        history = _recent_liked_ratings(user)
        prompt = _build_prompt(movie, history)
        return self._complete(prompt, movie, DEFAULT_MAX_OUTPUT_TOKENS)

    def generate_joint(self, users, movie: Movie) -> str:
        histories = [
            _recent_liked_ratings(user, JOINT_MAX_HISTORY_MOVIES) for user in users
        ]
        prompt = _build_joint_prompt(movie, histories)
        return self._complete(prompt, movie, JOINT_MAX_OUTPUT_TOKENS)

    def _complete(self, prompt: str, movie: Movie, max_output_tokens: int) -> str:
        try:
            return self.complete(
                prompt,
                max_output_tokens=max_output_tokens,
                label=f"justification for movie {movie.pk}",
            ).text
        except AIUnavailableError as exc:
            raise JustificationUnavailableError from exc


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


def ensure_joint_justification(
    candidate: SwipeSessionCandidate,
    users,
) -> CandidateJustification:
    with transaction.atomic():
        locked = (
            SwipeSessionCandidate.objects.select_for_update(of=("self",))
            .select_related("movie")
            .get(pk=candidate.pk)
        )

        justification = getattr(locked, "justification", None)
        if justification is not None and justification.text:
            return justification

        client = JustificationClient()
        text = client.generate_joint(users=users, movie=locked.movie)

        justification, _ = CandidateJustification.objects.update_or_create(
            candidate=locked,
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
    session = get_user_swipe_session(session_id=session_id, user=user)
    ensure_session_active(session)

    try:
        candidate = SwipeSessionCandidate.objects.get(
            pk=candidate_id,
            session=session,
        )
    except SwipeSessionCandidate.DoesNotExist as exc:
        raise CandidateNotFoundError from exc

    if session.type == SwipeSessionType.PAIRED:
        justification = ensure_joint_justification(
            candidate=candidate,
            users=list(session.users.all()),
        )
    else:
        justification = ensure_candidate_justification(
            candidate=candidate,
            user=user,
        )

    return candidate, justification


def _recent_liked_ratings(user, limit: int = DEFAULT_MAX_HISTORY_MOVIES) -> list[Rating]:
    return list(
        Rating.objects.filter(user=user, rating__isnull=False)
        .order_by("-rating", "-watched_date")[:limit]
    )


def _history_lines(history: list[Rating]) -> str:
    return "\n".join(
        f"- {r.title} ({r.release_year}): {r.rating}/5" for r in history
    ) or "No rating history yet."


def _build_prompt(movie: Movie, history: list[Rating]) -> str:
    return (
        "You are a movie recommendation assistant. In 1-2 sentences, explain "
        "why this movie might appeal to this user, referring specifically "
        "to some of their previous ratings. Do not invent any information "
        "that does not appear in the rating history. "
        f"Candidate movie: {movie.title} ({movie.release_year})\n"
        f"Synopsis/description: {movie.wikidata_description}\n"
        f"Genres: {', '.join(g.name for g in movie.genres.all())}\n\n"
        f"User's rating history:\n{_history_lines(history)}"
    )


def _build_joint_prompt(movie: Movie, histories: list[list[Rating]]) -> str:
    people = "\n\n".join(
        f"Person {letter}'s rating history:\n{_history_lines(history)}"
        for letter, history in zip("AB", histories)
    )

    return (
        "You are a movie recommendation assistant. Two people are choosing a "
        "movie to watch together. In 1-2 sentences, explain why this movie "
        "suits both of them, referring specifically to some of their previous "
        "ratings, ideally something one of them loved and something the other "
        "did. Do not invent any information that does not appear in the rating "
        "histories. Both people will read the same text, so say 'one of you' "
        "and 'the other'; never use the labels A/B or any names. "
        f"Candidate movie: {movie.title} ({movie.release_year})\n"
        f"Synopsis/description: {movie.wikidata_description}\n"
        f"Genres: {', '.join(g.name for g in movie.genres.all())}\n\n"
        f"{people}"
    )
