from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.swipe_sessions.models import SwipeSessionCandidate
from apps.swipe_sessions.services.candidate_pool import fill_candidate_pool


@pytest.mark.django_db
def test_fill_candidate_pool_creates_candidates(user, swipe_session, movie):
    candidates = [
        SimpleNamespace(movie=movie, final_score=0.85),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ) as build_pool:
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    build_pool.assert_called_once_with(user)

    assert len(result) == 1

    candidate = result[0]

    assert candidate.session == swipe_session
    assert candidate.movie == movie
    assert candidate.score == 0.85
    assert candidate.position == 1

    assert SwipeSessionCandidate.objects.filter(
        session=swipe_session,
        movie=movie,
    ).exists()


@pytest.mark.django_db
def test_fill_candidate_pool_ignores_existing_movies(
    user,
    swipe_session,
    movie,
    another_movie,
):
    SwipeSessionCandidate.objects.create(
        session=swipe_session,
        movie=movie,
        score=0.90,
        position=1,
    )

    candidates = [
        SimpleNamespace(movie=movie, final_score=0.95),
        SimpleNamespace(movie=another_movie, final_score=0.80),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert len(result) == 1

    candidate = result[0]

    assert candidate.movie == another_movie
    assert candidate.score == 0.80
    assert candidate.position == 2

    assert SwipeSessionCandidate.objects.filter(
        session=swipe_session,
    ).count() == 2


@pytest.mark.django_db
def test_fill_candidate_pool_continues_positions(
    user,
    swipe_session,
    movie,
    another_movie,
):
    SwipeSessionCandidate.objects.create(
        session=swipe_session,
        movie=movie,
        score=0.90,
        position=5,
    )

    candidates = [
        SimpleNamespace(movie=another_movie, final_score=0.80),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert len(result) == 1
    assert result[0].position == 6


@pytest.mark.django_db
def test_fill_candidate_pool_creates_sequential_positions(
    user,
    swipe_session,
    movie,
    another_movie,
):
    candidates = [
        SimpleNamespace(movie=movie, final_score=0.90),
        SimpleNamespace(movie=another_movie, final_score=0.75),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert [candidate.position for candidate in result] == [1, 2]


@pytest.mark.django_db
def test_fill_candidate_pool_returns_empty_when_no_candidates(
    user,
    swipe_session,
):
    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=[],
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert result == []
    assert not SwipeSessionCandidate.objects.filter(
        session=swipe_session,
    ).exists()


@pytest.mark.django_db
def test_fill_candidate_pool_returns_empty_when_all_movies_exist(
    user,
    swipe_session,
    movie,
):
    SwipeSessionCandidate.objects.create(
        session=swipe_session,
        movie=movie,
        score=0.90,
        position=1,
    )

    candidates = [
        SimpleNamespace(movie=movie, final_score=0.95),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert result == []

    assert SwipeSessionCandidate.objects.filter(
        session=swipe_session,
    ).count() == 1
