from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from apps.common.enums import SwipeAction
from apps.recommendations.services.taste_profile import (
    LIKED_BOOST,
    MIN_RATING_TO_COUNT,
    NEGATIVE_RATING_SCALE,
    RATING_BASELINE,
    SWIPE_ACTION_WEIGHTS,
    SWIPE_HALF_LIFE_DAYS,
    SWIPE_WEIGHT_SCALE,
    _rating_vectors_and_weights,
    _recency_weight,
    _swipe_vectors_and_weights,
    build_taste_profile,
)

MODULE = "apps.recommendations.services.taste_profile"
NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
USER = SimpleNamespace(pk=42)


@pytest.fixture(autouse=True)
def frozen_now():
    with patch(f"{MODULE}.timezone.now", return_value=NOW):
        yield


class Sources:
    def __init__(self, rating_model, swipe_model):
        self.rating_model = rating_model
        self.swipe_model = swipe_model

    def ratings(self, *items):
        self.rating_model.objects.filter.return_value.select_related.return_value = list(items)

    def swipes(self, *items):
        self.swipe_model.objects.filter.return_value.select_related.return_value = list(items)


@pytest.fixture
def sources():
    with patch(f"{MODULE}.Rating") as rating_model, patch(f"{MODULE}.Swipe") as swipe_model:
        source = Sources(rating_model, swipe_model)
        source.ratings()
        source.swipes()
        yield source


def rated(value, vector, *, liked=False):
    return SimpleNamespace(
        rating=value, liked=liked, movie=SimpleNamespace(embedding=vector)
    )


def swiped(action, vector, *, days_ago=0):
    return SimpleNamespace(
        action=action,
        created_at=NOW - timedelta(days=days_ago),
        candidate=SimpleNamespace(movie=SimpleNamespace(embedding=vector)),
    )


class TestRecencyWeight:
    def test_a_brand_new_event_has_full_weight(self):
        assert _recency_weight(NOW, 60.0) == pytest.approx(1.0)

    @pytest.mark.parametrize(
        ("days", "expected"), [(60, 0.5), (120, 0.25), (180, 0.125)]
    )
    def test_weight_halves_every_half_life(self, days, expected):
        assert _recency_weight(NOW - timedelta(days=days), 60.0) == pytest.approx(expected)

    def test_half_life_is_configurable(self):
        assert _recency_weight(NOW - timedelta(days=10), 10.0) == pytest.approx(0.5)

    def test_older_events_weigh_less(self):
        recent = _recency_weight(NOW - timedelta(days=5), 60.0)
        old = _recency_weight(NOW - timedelta(days=50), 60.0)

        assert recent > old > 0


class TestRatingVectorsAndWeights:
    @pytest.mark.parametrize(
        ("value", "liked", "expected"),
        [
            (4.0, False, 4.0 - RATING_BASELINE),
            (5.0, False, 5.0 - RATING_BASELINE),
            (RATING_BASELINE, False, 0.0),
            (1.0, False, (1.0 - RATING_BASELINE) * NEGATIVE_RATING_SCALE),
            (0.5, False, (0.5 - RATING_BASELINE) * NEGATIVE_RATING_SCALE),
            (4.0, True, (4.0 - RATING_BASELINE) + LIKED_BOOST),
            (5.0, True, (5.0 - RATING_BASELINE) + LIKED_BOOST),
            (1.0, True, LIKED_BOOST),
        ],
    )
    def test_weight_of_a_rating(self, sources, value, liked, expected):
        sources.ratings(rated(value, [1.0, 0.0], liked=liked))

        _, weights = _rating_vectors_and_weights(USER)

        assert weights == [pytest.approx(expected)]

    def test_a_liked_film_never_gets_a_negative_weight(self, sources):
        sources.ratings(rated(0.5, [1.0, 0.0], liked=True))

        _, weights = _rating_vectors_and_weights(USER)

        assert weights[0] > 0

    def test_vectors_are_float32_arrays_in_the_same_order(self, sources):
        sources.ratings(rated(4.0, [1.0, 0.0]), rated(5.0, [0.0, 1.0]))

        vectors, weights = _rating_vectors_and_weights(USER)

        assert [v.dtype for v in vectors] == [np.float32, np.float32]
        np.testing.assert_array_equal(vectors[0], [1.0, 0.0])
        np.testing.assert_array_equal(vectors[1], [0.0, 1.0])
        assert len(weights) == 2

    def test_no_ratings_gives_empty_lists(self, sources):
        assert _rating_vectors_and_weights(USER) == ([], [])

    def test_only_usable_ratings_are_queried(self, sources):
        _rating_vectors_and_weights(USER)

        sources.rating_model.objects.filter.assert_called_once_with(
            user=USER,
            movie__isnull=False,
            movie__embedding__isnull=False,
            rating__gte=MIN_RATING_TO_COUNT,
        )
        sources.rating_model.objects.filter.return_value.select_related.assert_called_once_with(
            "movie"
        )


class TestSwipeVectorsAndWeights:
    @pytest.mark.parametrize("action", list(SWIPE_ACTION_WEIGHTS))
    @pytest.mark.parametrize("days_ago", [0, 30, 60, 120])
    def test_weight_combines_action_scale_and_recency(self, sources, action, days_ago):
        sources.swipes(swiped(action, [1.0, 0.0], days_ago=days_ago))

        _, weights = _swipe_vectors_and_weights(USER)

        expected = (
            SWIPE_WEIGHT_SCALE
            * SWIPE_ACTION_WEIGHTS[action]
            * 0.5 ** (days_ago / SWIPE_HALF_LIFE_DAYS)
        )
        assert weights == [pytest.approx(expected)]

    def test_watchlist_pulls_towards_the_film_and_skip_pushes_away(self, sources):
        sources.swipes(
            swiped(SwipeAction.WATCHLIST, [1.0, 0.0]),
            swiped(SwipeAction.SKIP, [0.0, 1.0]),
        )

        _, weights = _swipe_vectors_and_weights(USER)

        assert weights[0] > 0
        assert weights[1] < 0

    def test_vectors_are_float32_arrays(self, sources):
        sources.swipes(swiped(SwipeAction.WATCHLIST, [0.5, 0.5]))

        vectors, _ = _swipe_vectors_and_weights(USER)

        assert vectors[0].dtype == np.float32

    def test_no_swipes_gives_empty_lists(self, sources):
        assert _swipe_vectors_and_weights(USER) == ([], [])

    def test_only_weighted_actions_on_embedded_films_are_queried(self, sources):
        _swipe_vectors_and_weights(USER)

        kwargs = sources.swipe_model.objects.filter.call_args.kwargs
        assert kwargs["user"] == USER
        assert set(kwargs["action__in"]) == set(SWIPE_ACTION_WEIGHTS)
        assert kwargs["candidate__movie__isnull"] is False
        assert kwargs["candidate__movie__embedding__isnull"] is False
        sources.swipe_model.objects.filter.return_value.select_related.assert_called_once_with(
            "candidate__movie"
        )


class TestBuildTasteProfile:
    def test_returns_none_without_any_data(self, sources, caplog):
        with caplog.at_level(logging.INFO):
            assert build_taste_profile(USER) is None

        assert "no taste profile" in caplog.text
        assert "42" in caplog.text

    def test_returns_none_when_every_weight_is_zero(self, sources):
        sources.ratings(rated(RATING_BASELINE, [1.0, 0.0]))

        assert build_taste_profile(USER) is None

    def test_single_rating_gives_that_films_vector(self, sources):
        sources.ratings(rated(5.0, [0.0, 1.0]))

        np.testing.assert_allclose(build_taste_profile(USER), [0.0, 1.0])

    def test_positive_ratings_are_averaged_by_weight(self, sources):
        sources.ratings(rated(4.0, [1.0, 0.0]), rated(5.0, [0.0, 1.0]))

        profile = build_taste_profile(USER)

        np.testing.assert_allclose(profile, [1.5 / 4.0, 2.5 / 4.0], rtol=1e-5)

    def test_liked_films_weigh_more_than_plain_ratings(self, sources):
        sources.ratings(
            rated(4.0, [1.0, 0.0], liked=True), rated(4.0, [0.0, 1.0])
        )

        profile = build_taste_profile(USER)

        assert profile[0] > profile[1]

    def test_negative_ratings_are_subtracted(self, sources):
        sources.ratings(rated(5.0, [1.0, 0.0]), rated(0.5, [0.0, 1.0]))

        np.testing.assert_allclose(build_taste_profile(USER), [1.0, -1.0], rtol=1e-5)

    def test_only_negative_ratings_point_away_from_them(self, sources):
        sources.ratings(rated(0.5, [0.0, 1.0]))

        np.testing.assert_allclose(build_taste_profile(USER), [0.0, -1.0])

    def test_negative_ratings_are_averaged_by_magnitude(self, sources):
        sources.ratings(rated(1.0, [1.0, 0.0]), rated(0.5, [0.0, 1.0]))

        w1 = abs((1.0 - RATING_BASELINE) * NEGATIVE_RATING_SCALE)
        w2 = abs((0.5 - RATING_BASELINE) * NEGATIVE_RATING_SCALE)
        expected = -np.array([w1, w2]) / (w1 + w2)
        np.testing.assert_allclose(build_taste_profile(USER), expected, rtol=1e-5)

    def test_zero_weight_films_do_not_influence_the_profile(self, sources):
        sources.ratings(
            rated(4.0, [1.0, 0.0]), rated(RATING_BASELINE, [0.0, 1.0])
        )

        np.testing.assert_allclose(build_taste_profile(USER), [1.0, 0.0])

    def test_swipes_alone_can_build_a_profile(self, sources):
        sources.swipes(swiped(SwipeAction.WATCHLIST, [0.0, 1.0]))

        np.testing.assert_allclose(build_taste_profile(USER), [0.0, 1.0])

    def test_skips_alone_point_away_from_the_skipped_film(self, sources):
        sources.swipes(swiped(SwipeAction.SKIP, [1.0, 0.0]))

        np.testing.assert_allclose(build_taste_profile(USER), [-1.0, 0.0])

    def test_ratings_and_swipes_are_combined(self, sources):
        sources.ratings(rated(4.0, [1.0, 0.0]))
        sources.swipes(swiped(SwipeAction.WATCHLIST, [0.0, 1.0]))

        w_rating = 4.0 - RATING_BASELINE
        w_swipe = SWIPE_WEIGHT_SCALE * SWIPE_ACTION_WEIGHTS[SwipeAction.WATCHLIST]
        expected = np.array([w_rating, w_swipe]) / (w_rating + w_swipe)
        np.testing.assert_allclose(build_taste_profile(USER), expected, rtol=1e-5)

    def test_recent_swipes_weigh_more_than_old_ones(self, sources):
        sources.swipes(
            swiped(SwipeAction.WATCHLIST, [1.0, 0.0], days_ago=0),
            swiped(SwipeAction.WATCHLIST, [0.0, 1.0], days_ago=SWIPE_HALF_LIFE_DAYS),
        )

        profile = build_taste_profile(USER)

        np.testing.assert_allclose(profile, [2 / 3, 1 / 3], rtol=1e-5)

    def test_a_skip_subtracts_from_a_positive_profile(self, sources):
        sources.ratings(rated(4.0, [1.0, 0.0]))
        sources.swipes(swiped(SwipeAction.SKIP, [0.0, 1.0]))

        np.testing.assert_allclose(build_taste_profile(USER), [1.0, -1.0], rtol=1e-5)

    def test_profile_is_a_float32_array(self, sources):
        sources.ratings(rated(5.0, [1.0, 0.0]), rated(0.5, [0.0, 1.0]))

        assert build_taste_profile(USER).dtype == np.float32
