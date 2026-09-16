from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.swipe_sessions.exceptions import (
    NotSessionMemberError,
    SwipeSessionNotFoundError,
)
from apps.swipe_sessions.models import CandidateJustification, Swipe, SwipeSessionCandidate
from apps.swipe_sessions.services.recommendation import (
    DEFAULT_POOL_REFILL_THRESHOLD,
    get_next_recommendation,
    get_next_recommendation_for_session,
)


class TestGetNextRecommendation:
    @pytest.mark.django_db
    def test_returns_first_unswiped_candidate(
        self,
        user,
        swipe_session,
        movie,
        another_movie,
    ):
        first_candidate = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=movie,
            score=0.90,
            position=1,
        )
        SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=another_movie,
            score=0.80,
            position=2,
        )

        result = get_next_recommendation(
            session=swipe_session,
            user=user,
        )

        assert result is not None

        candidate, recommendation = result

        assert candidate == first_candidate
        assert recommendation.movie == movie
        assert recommendation.similarity == 0.90
        assert recommendation.justification == ""

    @pytest.mark.django_db
    def test_skips_swiped_candidates(
        self,
        user,
        swipe_session,
        movie,
        another_movie,
    ):
        first_candidate = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=movie,
            score=0.90,
            position=1,
        )
        second_candidate = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=another_movie,
            score=0.80,
            position=2,
        )

        Swipe.objects.create(
            user=user,
            candidate=first_candidate,
            action="SKIP",
        )

        result = get_next_recommendation(
            session=swipe_session,
            user=user,
        )

        assert result is not None

        candidate, recommendation = result

        assert candidate == second_candidate
        assert recommendation.movie == another_movie
        assert recommendation.similarity == 0.80

    @pytest.mark.django_db
    def test_returns_candidates_in_position_order(
        self,
        user,
        swipe_session,
        movie,
        another_movie,
    ):
        candidate_one = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=movie,
            score=0.70,
            position=2,
        )
        candidate_two = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=another_movie,
            score=0.90,
            position=1,
        )

        result = get_next_recommendation(
            session=swipe_session,
            user=user,
        )

        assert result is not None
        candidate, _ = result

        assert candidate == candidate_two
        assert candidate != candidate_one

    @pytest.mark.django_db
    def test_returns_none_when_pool_is_empty_after_refill(
        self,
        user,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.services.recommendation.fill_candidate_pool"
        ) as fill_pool:
            result = get_next_recommendation(
                session=swipe_session,
                user=user,
            )

        assert result is None

        fill_pool.assert_called_once_with(
            session=swipe_session,
            user=user,
        )

    @pytest.mark.django_db
    def test_refills_pool_when_no_candidate_is_available(
        self,
        user,
        swipe_session,
        movie,
    ):
        candidate = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=movie,
            score=0.85,
            position=1,
        )

        Swipe.objects.create(
            user=user,
            candidate=candidate,
            action="SKIP",
        )

        new_movie = another_movie = SimpleNamespace(
            id=999,
        )

        new_candidate = SimpleNamespace(
            movie=new_movie,
            final_score=0.95,
        )

        with patch(
            "apps.swipe_sessions.services.recommendation.fill_candidate_pool"
        ) as fill_pool:
            fill_pool.side_effect = lambda session, user: None

            result = get_next_recommendation(
                session=swipe_session,
                user=user,
            )

        assert result is None

        fill_pool.assert_called_once_with(
            session=swipe_session,
            user=user,
        )

    @pytest.mark.django_db
    def test_refills_pool_when_remaining_candidates_reach_threshold(
        self,
        user,
        swipe_session,
        movie,
        another_movie,
    ):
        for position, current_movie in enumerate(
            [movie, another_movie],
            start=1,
        ):
            SwipeSessionCandidate.objects.create(
                session=swipe_session,
                movie=current_movie,
                score=0.80,
                position=position,
            )

        with patch(
            "apps.swipe_sessions.services.recommendation.fill_candidate_pool"
        ) as fill_pool:
            result = get_next_recommendation(
                session=swipe_session,
                user=user,
            )

        assert result is not None

        candidate, _ = result

        assert candidate.position == 1

        fill_pool.assert_called_once_with(
            session=swipe_session,
            user=user,
        )

    @pytest.mark.django_db
    @override_settings(POOL_REFILL_THRESHOLD=1)
    def test_does_not_refill_when_remaining_candidates_are_above_threshold(
        self,
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
        SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=another_movie,
            score=0.80,
            position=2,
        )

        with patch(
            "apps.swipe_sessions.services.recommendation.fill_candidate_pool"
        ) as fill_pool:
            result = get_next_recommendation(
                session=swipe_session,
                user=user,
            )

        assert result is not None
        fill_pool.assert_not_called()

    @pytest.mark.django_db
    def test_uses_custom_refill_threshold(
        self,
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
        SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=another_movie,
            score=0.80,
            position=2,
        )

        with (
            override_settings(POOL_REFILL_THRESHOLD=2),
            patch(
                "apps.swipe_sessions.services.recommendation.fill_candidate_pool"
            ) as fill_pool,
        ):
            result = get_next_recommendation(
                session=swipe_session,
                user=user,
            )

        assert result is not None
        fill_pool.assert_called_once_with(
            session=swipe_session,
            user=user,
        )

    @pytest.mark.django_db
    def test_includes_existing_justification(
        self,
        user,
        swipe_session,
        movie,
    ):
        candidate = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=movie,
            score=0.90,
            position=1,
        )

        CandidateJustification.objects.create(
            candidate=candidate,
            text="You liked similar movies.",
        )

        with override_settings(POOL_REFILL_THRESHOLD=0):
            result = get_next_recommendation(
                session=swipe_session,
                user=user,
            )

        assert result is not None

        candidate_result, recommendation = result

        assert candidate_result == candidate
        assert recommendation.justification == "You liked similar movies."

    @pytest.mark.django_db
    def test_uses_empty_justification_when_none_exists(
        self,
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

        result = get_next_recommendation(
            session=swipe_session,
            user=user,
        )

        assert result is not None

        _, recommendation = result

        assert recommendation.justification == ""


class TestGetNextRecommendationForSession:
    @pytest.mark.django_db
    def test_raises_when_session_does_not_exist(self, user):
        with pytest.raises(SwipeSessionNotFoundError):
            get_next_recommendation_for_session(
                session_id=999999,
                user=user,
            )

    @pytest.mark.django_db
    def test_raises_when_user_is_not_session_member(
        self,
        user,
        swipe_session,
    ):
        with pytest.raises(NotSessionMemberError):
            get_next_recommendation_for_session(
                session_id=swipe_session.pk,
                user=user,
            )

    @pytest.mark.django_db
    def test_delegates_to_get_next_recommendation(
        self,
        user,
        swipe_session,
    ):
        swipe_session.users.add(user)

        expected_result = MagicMock()

        with patch(
            "apps.swipe_sessions.services.recommendation.get_next_recommendation",
            return_value=expected_result,
        ) as get_recommendation:
            result = get_next_recommendation_for_session(
                session_id=swipe_session.pk,
                user=user,
            )

        assert result == expected_result

        get_recommendation.assert_called_once_with(
            session=swipe_session,
            user=user,
        )
