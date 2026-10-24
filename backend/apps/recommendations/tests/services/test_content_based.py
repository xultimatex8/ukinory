from __future__ import annotations

import itertools
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from apps.common.enums import SwipeAction
from apps.library.models import Rating, WatchlistEntry
from apps.movies.models import Movie
from apps.recommendations.services.content_based import (
    DEFAULT_SWIPE_COOLDOWN_DAYS,
    SWIPE_COOLDOWN_DAYS,
    _excluded_movie_ids,
    _recently_swiped_movie_ids,
    build_candidate_pool,
)

MODULE = "apps.recommendations.services.content_based"
NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
USER = SimpleNamespace(pk=7)

DIMS = Movie._meta.get_field("embedding").dimensions
_tmdb_ids = itertools.count(930000)


def vec(*values):
    return [float(v) for v in values] + [0.0] * (DIMS - len(values))


def make_movie(title, embedding):
    return Movie.objects.create(
        tmdb_id=next(_tmdb_ids), title=title, release_year=2000, embedding=embedding
    )


@pytest.fixture
def frozen_now():
    with patch(f"{MODULE}.timezone.now", return_value=NOW):
        yield


def queryset_returning(ids):
    queryset = MagicMock()
    queryset.values_list.return_value = ids
    return queryset


class TestRecentlySwipedMovieIds:
    def test_uses_a_cooldown_per_action_and_a_default_for_the_rest(self, frozen_now):
        others = set(SwipeAction) - set(SWIPE_COOLDOWN_DAYS)
        querysets = [queryset_returning([n]) for n in range(1, len(SWIPE_COOLDOWN_DAYS) + 2)]

        with patch(f"{MODULE}.Swipe") as swipe:
            swipe.objects.filter.side_effect = querysets
            result = _recently_swiped_movie_ids(USER)

        expected_calls = [
            call(
                user=USER,
                action=action,
                created_at__gte=NOW - timedelta(days=days),
                candidate__movie__isnull=False,
            )
            for action, days in SWIPE_COOLDOWN_DAYS.items()
        ]
        if others:
            expected_calls.append(
                call(
                    user=USER,
                    action__in=others,
                    created_at__gte=NOW - timedelta(days=DEFAULT_SWIPE_COOLDOWN_DAYS),
                    candidate__movie__isnull=False,
                )
            )
        assert swipe.objects.filter.call_args_list == expected_calls
        assert result == set(range(1, len(expected_calls) + 1))

    def test_skips_stay_hidden_longer_than_other_actions(self):
        assert SWIPE_COOLDOWN_DAYS[SwipeAction.SKIP] > DEFAULT_SWIPE_COOLDOWN_DAYS

    def test_returns_the_movie_ids_of_the_swipes(self, frozen_now):
        expected_queries = len(SWIPE_COOLDOWN_DAYS) + (
            1 if set(SwipeAction) - set(SWIPE_COOLDOWN_DAYS) else 0
        )

        with patch(f"{MODULE}.Swipe") as swipe:
            swipe.objects.filter.side_effect = [
                queryset_returning([1, 2]) for _ in range(expected_queries)
            ]
            result = _recently_swiped_movie_ids(USER)

        assert result == {1, 2}

    def test_no_swipes_gives_an_empty_set(self, frozen_now):
        with patch(f"{MODULE}.Swipe") as swipe:
            swipe.objects.filter.return_value = queryset_returning([])
            assert _recently_swiped_movie_ids(USER) == set()


class TestExcludedMovieIds:
    def test_combines_rated_watchlisted_and_recently_swiped(self):
        with patch(f"{MODULE}.Rating") as rating_model, patch(
            f"{MODULE}.WatchlistEntry"
        ) as watchlist_model, patch(
            f"{MODULE}._recently_swiped_movie_ids", return_value={4}
        ):
            rating_model.objects.filter.return_value.values_list.return_value = [1, 2]
            watchlist_model.objects.filter.return_value.values_list.return_value = [2, 3]

            result = _excluded_movie_ids(USER)

        assert result == {1, 2, 3, 4}

    def test_only_matched_films_of_the_user_are_considered(self):
        with patch(f"{MODULE}.Rating") as rating_model, patch(
            f"{MODULE}.WatchlistEntry"
        ) as watchlist_model, patch(
            f"{MODULE}._recently_swiped_movie_ids", return_value=set()
        ) as swiped:
            rating_model.objects.filter.return_value.values_list.return_value = []
            watchlist_model.objects.filter.return_value.values_list.return_value = []

            _excluded_movie_ids(USER)

        rating_model.objects.filter.assert_called_once_with(user=USER, movie__isnull=False)
        watchlist_model.objects.filter.assert_called_once_with(
            user=USER, movie__isnull=False
        )
        swiped.assert_called_once_with(USER)


@pytest.mark.django_db
class TestBuildCandidatePoolWithoutProfile:
    def test_falls_back_to_the_newest_films_with_zero_similarity(self, user, caplog):
        oldest = make_movie("Oldest", vec(1, 0))
        middle = make_movie("Middle", vec(0, 1))
        newest = make_movie("Newest", vec(1, 1))

        with caplog.at_level(logging.INFO):
            pool = build_candidate_pool(user)

        assert [c.movie.pk for c in pool] == [newest.pk, middle.pk, oldest.pk]
        assert all(c.similarity == 0.0 for c in pool)
        assert "falling back" in caplog.text

    def test_fallback_respects_the_pool_size(self, user):
        for n in range(4):
            make_movie(f"Film {n}", vec(1, n))

        assert len(build_candidate_pool(user, pool_size=2)) == 2

    def test_fallback_skips_films_without_embedding(self, user):
        with_embedding = make_movie("With", vec(1, 0))
        make_movie("Without", None)

        pool = build_candidate_pool(user)

        assert [c.movie.pk for c in pool] == [with_embedding.pk]

    def test_fallback_skips_rated_and_watchlisted_films(self, user, another_user):
        rated = make_movie("Rated", vec(1, 0))
        watchlisted = make_movie("Watchlisted", vec(0, 1))
        others_rating = make_movie("Rated by someone else", vec(1, 1))
        free = make_movie("Free", vec(1, 2))
        Rating.objects.create(
            user=user, title=rated.title, release_year=2000, movie=rated,
            rating=None, liked=False,
        )
        WatchlistEntry.objects.create(
            user=user, title=watchlisted.title, release_year=2000, movie=watchlisted
        )
        Rating.objects.create(
            user=another_user, title=others_rating.title, release_year=2000,
            movie=others_rating, rating=4.0, liked=False,
        )

        pool = build_candidate_pool(user)

        assert {c.movie.pk for c in pool} == {others_rating.pk, free.pk}


@pytest.mark.django_db
class TestBuildCandidatePoolWithProfile:
    PROFILE = np.array(vec(1, 0), dtype=np.float32)

    @pytest.fixture(autouse=True)
    def _profile(self):
        with patch(f"{MODULE}.build_taste_profile", return_value=self.PROFILE):
            yield

    def _movies(self):
        # created worst-first so that insertion order differs from similarity order
        opposite = make_movie("Opposite", vec(-1, 0))
        orthogonal = make_movie("Orthogonal", vec(0, 1))
        diagonal = make_movie("Diagonal", vec(1, 1))
        identical = make_movie("Identical", vec(1, 0))
        return identical, diagonal, orthogonal, opposite

    def test_candidates_are_ranked_by_similarity_to_the_profile(self, user):
        identical, diagonal, orthogonal, opposite = self._movies()

        pool = build_candidate_pool(user)

        assert [c.movie.pk for c in pool] == [
            identical.pk, diagonal.pk, orthogonal.pk, opposite.pk,
        ]

    def test_pool_is_limited_to_the_pool_size(self, user):
        identical, diagonal, *_ = self._movies()

        pool = build_candidate_pool(user, pool_size=2)

        assert [c.movie.pk for c in pool] == [identical.pk, diagonal.pk]

    def test_similarity_is_one_minus_the_cosine_distance(self, user):
        identical, diagonal, orthogonal, opposite = self._movies()

        pool = {c.movie.pk: c.similarity for c in build_candidate_pool(user)}

        assert pool[identical.pk] == pytest.approx(1.0, abs=1e-5)
        assert pool[diagonal.pk] == pytest.approx(1 / 2**0.5, abs=1e-5)
        assert pool[orthogonal.pk] == pytest.approx(0.0, abs=1e-5)
        assert pool[opposite.pk] == pytest.approx(-1.0, abs=1e-5)

    def test_rated_and_watchlisted_films_are_excluded(self, user):
        identical, diagonal, orthogonal, _ = self._movies()
        Rating.objects.create(
            user=user, title=identical.title, release_year=2000, movie=identical,
            rating=5.0, liked=True,
        )
        WatchlistEntry.objects.create(
            user=user, title=diagonal.title, release_year=2000, movie=diagonal
        )

        pool = build_candidate_pool(user)

        assert identical.pk not in {c.movie.pk for c in pool}
        assert diagonal.pk not in {c.movie.pk for c in pool}
        assert orthogonal.pk in {c.movie.pk for c in pool}

    def test_recently_swiped_films_are_excluded(self, user):
        identical, diagonal, *_ = self._movies()

        with patch(
            f"{MODULE}._recently_swiped_movie_ids", return_value={identical.pk}
        ):
            pool = build_candidate_pool(user)

        assert identical.pk not in {c.movie.pk for c in pool}
        assert diagonal.pk in {c.movie.pk for c in pool}

    def test_films_without_embedding_are_never_candidates(self, user):
        make_movie("Without", None)
        with_embedding = make_movie("With", vec(1, 0))

        pool = build_candidate_pool(user)

        assert [c.movie.pk for c in pool] == [with_embedding.pk]
