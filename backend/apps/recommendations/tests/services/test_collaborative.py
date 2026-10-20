from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.library.models import Rating
from apps.movies.models import Movie
from apps.recommendations.services.collaborative import (
    DEFAULT_MAX_SIMILAR_USERS,
    DEFAULT_MIN_COMMON_MOVIES,
    DEFAULT_MIN_RATERS_FOR_CF,
    _cosine,
    build_rating_matrix,
    find_similar_users,
    predict_cf_score,
)

MODULE = "apps.recommendations.services.collaborative"


def matrix(by_user=None, by_movie=None):
    return SimpleNamespace(by_user=by_user or {}, by_movie=by_movie or {})


def ratings(*values, start=1):
    return {movie_id: value for movie_id, value in enumerate(values, start=start)}


class TestBuildRatingMatrix:
    def test_indexes_ratings_by_user_and_by_movie(self):
        rows = [
            {"user_id": 1, "movie_id": 10, "rating": 4.0},
            {"user_id": 1, "movie_id": 11, "rating": 2.0},
            {"user_id": 2, "movie_id": 10, "rating": 5.0},
        ]

        with patch(f"{MODULE}.Rating") as rating_model:
            rating_model.objects.filter.return_value.values.return_value = rows
            result = build_rating_matrix()

        assert result.by_user == {1: {10: 4.0, 11: 2.0}, 2: {10: 5.0}}
        assert result.by_movie == {10: {1: 4.0, 2: 5.0}, 11: {1: 2.0}}

    def test_empty_ratings_give_an_empty_matrix(self):
        with patch(f"{MODULE}.Rating") as rating_model:
            rating_model.objects.filter.return_value.values.return_value = []
            result = build_rating_matrix()

        assert result.by_user == {}
        assert result.by_movie == {}

    def test_only_rated_and_matched_films_are_queried(self):
        with patch(f"{MODULE}.Rating") as rating_model:
            rating_model.objects.filter.return_value.values.return_value = []
            build_rating_matrix()

        rating_model.objects.filter.assert_called_once_with(
            movie__isnull=False, rating__isnull=False
        )
        rating_model.objects.filter.return_value.values.assert_called_once_with(
            "user_id", "movie_id", "rating"
        )

    def test_the_last_row_wins_for_a_repeated_user_and_film(self):
        rows = [
            {"user_id": 1, "movie_id": 10, "rating": 2.0},
            {"user_id": 1, "movie_id": 10, "rating": 4.5},
        ]

        with patch(f"{MODULE}.Rating") as rating_model:
            rating_model.objects.filter.return_value.values.return_value = rows
            result = build_rating_matrix()

        assert result.by_user == {1: {10: 4.5}}
        assert result.by_movie == {10: {1: 4.5}}


@pytest.mark.django_db
class TestBuildRatingMatrixWithDatabase:
    def test_skips_unmatched_and_unrated_entries(self, user, another_user):
        dune = Movie.objects.create(tmdb_id=910001, title="Dune", release_year=2021)
        Rating.objects.create(
            user=user, title="Dune", release_year=2021, movie=dune, rating=4.0, liked=False
        )
        Rating.objects.create(
            user=another_user, title="Dune", release_year=2021, movie=dune, rating=2.0, liked=False
        )
        Rating.objects.create(
            user=user, title="Unmatched", release_year=1999, movie=None, rating=3.0, liked=False
        )
        liked_only = Movie.objects.create(tmdb_id=910002, title="Liked only", release_year=2000)
        Rating.objects.create(
            user=another_user, title="Liked only", release_year=2000, movie=liked_only,
            rating=None, liked=True,
        )

        result = build_rating_matrix()

        assert result.by_user == {user.pk: {dune.pk: 4.0}, another_user.pk: {dune.pk: 2.0}}
        assert result.by_movie == {dune.pk: {user.pk: 4.0, another_user.pk: 2.0}}


class TestCosine:
    def test_identical_ratings_have_similarity_one(self):
        a = ratings(5, 4, 3, 2)

        assert _cosine(a, dict(a)) == pytest.approx(1.0)

    def test_proportional_ratings_have_similarity_one(self):
        assert _cosine(ratings(1, 2, 3, 4), ratings(2, 4, 6, 8)) == pytest.approx(1.0)

    def test_disjoint_tastes_have_similarity_zero(self):
        assert _cosine(ratings(1, 0, 1, 0), ratings(0, 1, 0, 1)) == pytest.approx(0.0)

    def test_known_value(self):
        a, b = ratings(5, 4, 3, 2), ratings(4, 4, 4, 4)

        assert _cosine(a, b) == pytest.approx(56 / ((54**0.5) * 8))

    def test_too_few_common_films_gives_none(self):
        a = ratings(5, 4, 3)
        b = ratings(5, 4, 3, 2, 1)

        assert len(set(a) & set(b)) == DEFAULT_MIN_COMMON_MOVIES - 1
        assert _cosine(a, b) is None

    def test_exactly_the_minimum_common_films_is_enough(self):
        assert _cosine(ratings(5, 4, 3, 2), ratings(5, 4, 3, 2)) is not None

    def test_minimum_is_configurable(self):
        a, b = ratings(5, 4), ratings(5, 4)

        assert _cosine(a, b) is None
        assert _cosine(a, b, min_common_movies=2) == pytest.approx(1.0)

    def test_only_common_films_are_compared(self):
        a = {**ratings(5, 4, 3, 2), 99: 0.5}
        b = {**ratings(5, 4, 3, 2), 98: 5.0}

        assert _cosine(a, b) == pytest.approx(1.0)

    def test_all_zero_ratings_give_none(self):
        assert _cosine(ratings(0, 0, 0, 0), ratings(5, 4, 3, 2)) is None


class TestFindSimilarUsers:
    TARGET = ratings(5, 4, 3, 2)

    def test_unknown_user_has_no_similar_users(self):
        assert find_similar_users(1, matrix(by_user={2: self.TARGET})) == []

    def test_user_without_ratings_has_no_similar_users(self):
        assert find_similar_users(1, matrix(by_user={1: {}, 2: self.TARGET})) == []

    def test_excludes_the_user_and_sorts_by_similarity(self):
        by_user = {
            1: self.TARGET,
            2: ratings(4, 4, 4, 4),
            3: dict(self.TARGET),
        }

        result = find_similar_users(1, matrix(by_user=by_user))

        assert [user_id for user_id, _ in result] == [3, 2]
        assert result[0][1] == pytest.approx(1.0)
        assert result[1][1] == pytest.approx(56 / ((54**0.5) * 8))

    def test_users_without_enough_common_films_are_dropped(self):
        by_user = {1: self.TARGET, 2: ratings(5, 4, 3), 3: dict(self.TARGET)}

        result = find_similar_users(1, matrix(by_user=by_user))

        assert [user_id for user_id, _ in result] == [3]

    def test_users_with_zero_or_negative_similarity_are_dropped(self):
        by_user = {
            1: ratings(1, 0, 1, 0),
            2: ratings(0, 1, 0, 1),
            3: ratings(1, 0, 1, 0),
        }

        result = find_similar_users(1, matrix(by_user=by_user))

        assert [user_id for user_id, _ in result] == [3]

    def test_result_is_limited_to_the_requested_amount(self):
        by_user = {1: self.TARGET}
        by_user.update({n: dict(self.TARGET) for n in range(2, 8)})

        result = find_similar_users(1, matrix(by_user=by_user), max_similar_users=3)

        assert len(result) == 3

    def test_default_limit(self):
        by_user = {1: self.TARGET}
        by_user.update(
            {n: dict(self.TARGET) for n in range(2, DEFAULT_MAX_SIMILAR_USERS + 5)}
        )

        assert len(find_similar_users(1, matrix(by_user=by_user))) == DEFAULT_MAX_SIMILAR_USERS


class TestPredictCfScore:
    def test_unknown_film_gives_none(self):
        assert predict_cf_score(1, matrix(), [(2, 0.9)]) is None

    def test_too_few_raters_gives_none(self):
        raters = {n: 4.0 for n in range(DEFAULT_MIN_RATERS_FOR_CF - 1)}
        similar = [(n, 0.9) for n in raters]

        assert predict_cf_score(1, matrix(by_movie={1: raters}), similar) is None

    def test_default_minimum_raters_is_enough(self):
        raters = {n: 4.0 for n in range(DEFAULT_MIN_RATERS_FOR_CF)}
        similar = [(n, 0.9) for n in raters]

        score = predict_cf_score(1, matrix(by_movie={1: raters}), similar)

        assert score == pytest.approx(4.0)

    def test_weighted_average_of_similar_users_ratings(self):
        raters = {10: 4.0, 11: 2.0, 12: 5.0}

        score = predict_cf_score(
            1,
            matrix(by_movie={1: raters}),
            [(10, 0.9), (11, 0.1)],
            min_raters_for_cf=3,
        )

        assert score == pytest.approx((0.9 * 4.0 + 0.1 * 2.0) / 1.0)

    def test_similar_users_who_did_not_rate_the_film_are_skipped(self):
        raters = {10: 4.0, 11: 2.0, 12: 5.0}

        score = predict_cf_score(
            1,
            matrix(by_movie={1: raters}),
            [(99, 0.99), (10, 0.5)],
            min_raters_for_cf=3,
        )

        assert score == pytest.approx(4.0)

    def test_no_overlap_with_similar_users_gives_none(self):
        raters = {10: 4.0, 11: 2.0, 12: 5.0}

        assert (
            predict_cf_score(
                1, matrix(by_movie={1: raters}), [(99, 0.9)], min_raters_for_cf=3
            )
            is None
        )

    def test_denominator_uses_absolute_similarities(self):
        raters = {10: 2.0, 11: 4.0, 12: 3.0}

        score = predict_cf_score(
            1,
            matrix(by_movie={1: raters}),
            [(10, -0.5), (11, 0.5)],
            min_raters_for_cf=3,
        )

        assert score == pytest.approx((-0.5 * 2.0 + 0.5 * 4.0) / 1.0)

    def test_zero_similarity_everywhere_gives_none(self):
        raters = {10: 4.0, 11: 2.0, 12: 5.0}

        assert (
            predict_cf_score(
                1, matrix(by_movie={1: raters}), [(10, 0.0)], min_raters_for_cf=3
            )
            is None
        )

    def test_minimum_raters_is_configurable(self):
        raters = {10: 4.0}

        score = predict_cf_score(
            1, matrix(by_movie={1: raters}), [(10, 0.8)], min_raters_for_cf=1
        )

        assert score == pytest.approx(4.0)
