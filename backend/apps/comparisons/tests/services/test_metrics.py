from __future__ import annotations

from collections import Counter

import numpy as np

from apps.comparisons.services.metrics import (
    DIVERGENCE_THRESHOLD,
    HIGH_RATING,
    PROFILE_TOP_FILMS,
    PROFILE_TOP_GENRES,
    TOP_N,
    _favourites_counter,
    _mean,
    _pearson,
    _ranked,
    _round,
    _top_shared,
    _user_profile,
    compute_metrics,
    cosine_similarity,
)
from apps.comparisons.services.snapshot import RatedFilm, UserLibrary
import pytest


class TestMetricsHelpers:
    def test_mean_returns_average(self):
        assert _mean([2.0, 4.0, 6.0]) == 4.0

    def test_mean_returns_none_for_empty_list(self):
        assert _mean([]) is None

    def test_pearson_returns_none_with_insufficient_pairs(self):
        xs = [1.0, 2.0]
        ys = [1.0, 2.0]

        assert _pearson(xs, ys) is None

    def test_pearson_returns_one_for_perfect_positive_correlation(self):
        xs = [1.0, 2.0, 3.0]
        ys = [2.0, 4.0, 6.0]

        assert _pearson(xs, ys) == pytest.approx(1.0)

    def test_pearson_returns_minus_one_for_perfect_negative_correlation(self):
        xs = [1.0, 2.0, 3.0]
        ys = [6.0, 4.0, 2.0]

        assert _pearson(xs, ys) == pytest.approx(-1.0)

    def test_pearson_returns_none_when_first_values_are_constant(self):
        xs = [4.0, 4.0, 4.0]
        ys = [1.0, 2.0, 3.0]

        assert _pearson(xs, ys) is None

    def test_pearson_returns_none_when_second_values_are_constant(self):
        xs = [1.0, 2.0, 3.0]
        ys = [4.0, 4.0, 4.0]

        assert _pearson(xs, ys) is None

    def test_cosine_similarity_returns_none_when_first_vector_is_none(self):
        result = cosine_similarity(
            None,
            np.array([1.0, 2.0]),
        )

        assert result is None

    def test_cosine_similarity_returns_none_when_second_vector_is_none(self):
        result = cosine_similarity(
            np.array([1.0, 2.0]),
            None,
        )

        assert result is None

    def test_cosine_similarity_returns_none_for_zero_vector(self):
        result = cosine_similarity(
            np.array([0.0, 0.0]),
            np.array([1.0, 2.0]),
        )

        assert result is None

    def test_cosine_similarity_returns_one_for_identical_vectors(self):
        result = cosine_similarity(
            np.array([1.0, 2.0]),
            np.array([1.0, 2.0]),
        )

        assert result == pytest.approx(1.0)

    def test_cosine_similarity_returns_zero_for_orthogonal_vectors(self):
        result = cosine_similarity(
            np.array([1.0, 0.0]),
            np.array([0.0, 1.0]),
        )

        assert result == pytest.approx(0.0)

    def test_cosine_similarity_returns_minus_one_for_opposite_vectors(self):
        result = cosine_similarity(
            np.array([1.0, 0.0]),
            np.array([-1.0, 0.0]),
        )

        assert result == pytest.approx(-1.0)

    def test_round_returns_none_for_none(self):
        assert _round(None) is None

    def test_round_rounds_value(self):
        assert _round(0.123456) == 0.123

    def test_round_uses_custom_digits(self):
        assert _round(0.123456, 2) == 0.12

    def test_favourites_counter_includes_liked_films(self):
        films = {
            1: RatedFilm(
                title="Movie A",
                release_year=2020,
                rating=3.0,
                liked=True,
                genres=["Drama"],
                directors=["Director A"],
            ),
            2: RatedFilm(
                title="Movie B",
                release_year=2021,
                rating=2.0,
                liked=False,
                genres=["Comedy"],
                directors=["Director B"],
            ),
        }

        library = UserLibrary(
            user_id="user-a",
            films=films,
        )

        result = _favourites_counter(
            library,
            "genres",
        )

        assert result["Drama"] == 1
        assert "Comedy" not in result

    def test_favourites_counter_includes_high_rated_films(self):
        films = {
            1: RatedFilm(
                title="Movie A",
                release_year=2020,
                rating=HIGH_RATING,
                liked=False,
                genres=["Drama"],
                directors=["Director A"],
            ),
            2: RatedFilm(
                title="Movie B",
                release_year=2021,
                rating=3.5,
                liked=False,
                genres=["Comedy"],
                directors=["Director B"],
            ),
        }

        library = UserLibrary(
            user_id="user-a",
            films=films,
        )

        result = _favourites_counter(
            library,
            "genres",
        )

        assert result["Drama"] == 1
        assert "Comedy" not in result

    def test_favourites_counter_counts_genres_across_favourite_films(self):
        films = {
            1: RatedFilm(
                title="Movie A",
                release_year=2020,
                rating=5.0,
                liked=False,
                genres=["Drama", "Thriller"],
                directors=["Director A"],
            ),
            2: RatedFilm(
                title="Movie B",
                release_year=2021,
                rating=4.5,
                liked=False,
                genres=["Drama", "Comedy"],
                directors=["Director B"],
            ),
        }

        library = UserLibrary(
            user_id="user-a",
            films=films,
        )

        result = _favourites_counter(
            library,
            "genres",
        )

        assert result["Drama"] == 2
        assert result["Thriller"] == 1
        assert result["Comedy"] == 1

    def test_top_shared_returns_shared_items_ordered_by_frequency(self):
        lib_a = UserLibrary(
            user_id="a",
            films={
                1: RatedFilm(
                    title="A",
                    release_year=2020,
                    rating=5.0,
                    liked=False,
                    genres=["Drama", "Comedy"],
                    directors=["Director A"],
                ),
                2: RatedFilm(
                    title="B",
                    release_year=2021,
                    rating=5.0,
                    liked=False,
                    genres=["Drama"],
                    directors=["Director B"],
                ),
            },
        )

        lib_b = UserLibrary(
            user_id="b",
            films={
                3: RatedFilm(
                    title="C",
                    release_year=2020,
                    rating=5.0,
                    liked=False,
                    genres=["Drama", "Comedy"],
                    directors=["Director A"],
                ),
                4: RatedFilm(
                    title="D",
                    release_year=2021,
                    rating=5.0,
                    liked=False,
                    genres=["Drama"],
                    directors=["Director C"],
                ),
            },
        )

        result = _top_shared(
            lib_a,
            lib_b,
            "genres",
        )

        assert result == ["Drama", "Comedy"]

    def test_top_shared_limits_result_to_top_n(self):
        genres = [
            "Action",
            "Comedy",
            "Drama",
            "Fantasy",
            "Horror",
            "Romance",
            "Sci-Fi",
        ]

        films_a = {}
        films_b = {}

        for index, genre in enumerate(genres):
            films_a[index] = RatedFilm(
                title=f"A{index}",
                release_year=2020,
                rating=5.0,
                liked=False,
                genres=[genre],
                directors=[],
            )

            films_b[index] = RatedFilm(
                title=f"B{index}",
                release_year=2020,
                rating=5.0,
                liked=False,
                genres=[genre],
                directors=[],
            )

        lib_a = UserLibrary(
            user_id="a",
            films=films_a,
        )
        lib_b = UserLibrary(
            user_id="b",
            films=films_b,
        )

        result = _top_shared(
            lib_a,
            lib_b,
            "genres",
        )

        assert len(result) == TOP_N


class TestComputeMetrics:
    def _library(self, user_id, films):
        return UserLibrary(
            user_id=user_id,
            films=films,
        )

    def _film(
        self,
        title,
        rating,
        *,
        year=2020,
        liked=False,
        genres=None,
        directors=None,
    ):
        return RatedFilm(
            title=title,
            release_year=year,
            rating=rating,
            liked=liked,
            genres=genres or [],
            directors=directors or [],
        )

    def test_compute_metrics_with_no_common_films(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Movie A",
                    5.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                2: self._film(
                    "Movie B",
                    4.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            np.array([1.0, 0.0]),
            np.array([1.0, 0.0]),
        )

        assert result.public["library_sizes"] == {
            "user-a": 1,
            "user-b": 1,
        }

        assert result.public["common_count"] == 0

        assert result.public["overlap_ratio"] == 0.0

        assert result.public["jaccard"] == 0.0

        assert result.public["mean_rating_gap"] is None

        assert result.public["rating_correlation"] is None

        assert result.public["agreements"] == []

        assert result.public["divergences"] == []

    def test_compute_metrics_calculates_common_movies_and_overlap(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Dune",
                    5.0,
                ),
                2: self._film(
                    "Alien",
                    4.0,
                ),
                3: self._film(
                    "Barbie",
                    3.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Dune",
                    4.0,
                ),
                2: self._film(
                    "Alien",
                    5.0,
                ),
                4: self._film(
                    "Oppenheimer",
                    5.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert result.public["common_count"] == 2

        assert result.public["overlap_ratio"] == 0.667

        assert result.public["jaccard"] == 0.5

    def test_compute_metrics_calculates_mean_rating_gap(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Movie A",
                    5.0,
                ),
                2: self._film(
                    "Movie B",
                    4.0,
                ),
                3: self._film(
                    "Movie C",
                    2.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Movie A",
                    4.0,
                ),
                2: self._film(
                    "Movie B",
                    3.0,
                ),
                3: self._film(
                    "Movie C",
                    1.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert result.public["mean_rating_gap"] == 1.0

    def test_compute_metrics_calculates_rating_correlation(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Movie A",
                    1.0,
                ),
                2: self._film(
                    "Movie B",
                    2.0,
                ),
                3: self._film(
                    "Movie C",
                    3.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Movie A",
                    2.0,
                ),
                2: self._film(
                    "Movie B",
                    4.0,
                ),
                3: self._film(
                    "Movie C",
                    6.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert result.public["rating_correlation"] == 1.0

    def test_compute_metrics_does_not_calculate_correlation_with_too_few_pairs(
        self,
    ):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Movie A",
                    5.0,
                ),
                2: self._film(
                    "Movie B",
                    4.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Movie A",
                    4.0,
                ),
                2: self._film(
                    "Movie B",
                    3.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert result.public["rating_correlation"] is None

    def test_compute_metrics_excludes_unrated_common_films_from_rating_stats(
        self,
    ):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Rated",
                    5.0,
                ),
                2: self._film(
                    "Unrated",
                    None,
                ),
                3: self._film(
                    "Rated 2",
                    4.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Rated",
                    4.0,
                ),
                2: self._film(
                    "Unrated",
                    1.0,
                ),
                3: self._film(
                    "Rated 2",
                    3.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert result.public["mean_rating_gap"] == 1.0

        assert result.public["rating_correlation"] is None

    def test_compute_metrics_detects_agreements(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Dune",
                    5.0,
                ),
                2: self._film(
                    "Alien",
                    4.5,
                ),
                3: self._film(
                    "Barbie",
                    3.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Dune",
                    5.0,
                ),
                2: self._film(
                    "Alien",
                    4.0,
                ),
                3: self._film(
                    "Barbie",
                    5.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert [item["title"] for item in result.public["agreements"]] == ["Dune", "Alien"]

    def test_compute_metrics_detects_divergences(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Dune",
                    5.0,
                ),
                2: self._film(
                    "Alien",
                    4.0,
                ),
                3: self._film(
                    "Barbie",
                    2.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Dune",
                    1.0,
                ),
                2: self._film(
                    "Alien",
                    4.0,
                ),
                3: self._film(
                    "Barbie",
                    5.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert [item["title"] for item in result.public["divergences"]] == ["Dune", "Barbie"]

    def test_compute_metrics_includes_ratings_with_user_ids(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Dune",
                    5.0,
                    year=2021,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Dune",
                    4.0,
                    year=2021,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert result.public["agreements"] == [
            {
                "movie_id": None,
                "title": "Dune",
                "release_year": 2021,
                "ratings": {
                    "user-a": 5.0,
                    "user-b": 4.0,
                },
            }
        ]

        assert result.public["divergences"] == []

    def test_compute_metrics_calculates_taste_similarity(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Dune",
                    5.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Dune",
                    5.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            np.array([1.0, 0.0]),
            np.array([1.0, 0.0]),
        )

        assert result.public["taste_similarity"] == 1.0

    def test_compute_metrics_omits_taste_similarity_when_embeddings_missing(
        self,
    ):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Dune",
                    5.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Dune",
                    5.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert result.public["taste_similarity"] is None

    def test_compute_metrics_calculates_compatibility_score(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Dune",
                    5.0,
                ),
                2: self._film(
                    "Alien",
                    4.0,
                ),
                3: self._film(
                    "Barbie",
                    3.0,
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Dune",
                    4.0,
                ),
                2: self._film(
                    "Alien",
                    3.0,
                ),
                3: self._film(
                    "Barbie",
                    2.0,
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            np.array([1.0, 0.0]),
            np.array([1.0, 0.0]),
        )

        assert result.public["compatibility_score"] is not None

        assert result.public["compatibility_score"] >= 0

        assert result.public["compatibility_score"] <= 100

    def test_compute_metrics_uses_shared_genres_and_directors(self):
        lib_a = self._library(
            "user-a",
            {
                1: self._film(
                    "Dune",
                    5.0,
                    genres=["Sci-Fi", "Drama"],
                    directors=["Denis Villeneuve"],
                ),
            },
        )

        lib_b = self._library(
            "user-b",
            {
                1: self._film(
                    "Dune",
                    5.0,
                    genres=["Sci-Fi"],
                    directors=["Denis Villeneuve"],
                ),
            },
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert result.internal["shared_genres"] == ["Sci-Fi"]

        assert result.internal["shared_directors"] == ["Denis Villeneuve"]

    def test_compute_metrics_returns_comparison_metrics_dataclass(self):
        lib_a = self._library(
            "user-a",
            {},
        )

        lib_b = self._library(
            "user-b",
            {},
        )

        result = compute_metrics(
            lib_a,
            lib_b,
            None,
            None,
        )

        assert isinstance(result.public, dict)

        assert isinstance(result.internal, dict)

        assert "compatibility_score" in result.public

        assert "shared_genres" in result.internal

        assert "shared_directors" in result.internal


def film(title, rating, *, year=2020, liked=False, movie_id=None,
         genres=(), directors=()):
    return RatedFilm(
        title=title,
        release_year=year,
        rating=rating,
        liked=liked,
        movie_id=movie_id,
        genres=frozenset(genres),
        directors=tuple(directors),
    )


def library(user_id, *films):
    return UserLibrary(
        user_id=user_id,
        films={(f.title.casefold(), f.release_year): f for f in films},
    )


class TestRanked:
    def test_orders_by_count_then_name(self):
        counter = Counter({"b": 2, "a": 2, "c": 3, "d": 1})

        assert _ranked(counter, 4) == ["c", "a", "b", "d"]

    def test_truncates_to_n(self):
        counter = Counter({"a": 3, "b": 2, "c": 1})

        assert _ranked(counter, 2) == ["a", "b"]

    def test_empty_counter_returns_empty_list(self):
        assert _ranked(Counter(), 3) == []


class TestUserProfile:
    def test_builds_profile_from_library(self):
        lib = library(
            "u1",
            film("A", 5.0, liked=True, genres={"Drama"}, directors=["X"]),
            film("B", 4.0, genres={"Drama", "Comedy"}, directors=["X", "Y"]),
            film("C", 2.0, genres={"Horror"}),
            film("D", None, liked=True, genres={"Horror"}),
        )

        profile = _user_profile(lib, [5.0, 3.0])

        assert profile["top_genres"] == ["Drama", "Comedy", "Horror"]
        assert profile["top_directors"] == ["X", "Y"]
        assert profile["mean_rating"] == 3.67
        assert profile["mean_rating_on_shared_films"] == 4.0
        assert profile["favourite_films"] == ["A", "B", "C"]

    def test_unrated_films_are_excluded_from_mean_and_favourites(self):
        lib = library("u1", film("A", 4.0), film("Z", None, liked=True))

        profile = _user_profile(lib, [])

        assert profile["mean_rating"] == 4.0
        assert profile["favourite_films"] == ["A"]

    def test_liked_film_wins_rating_tie_in_favourites(self):
        lib = library(
            "u1",
            film("Alpha", 4.0),
            film("Beta", 4.0, liked=True),
        )

        profile = _user_profile(lib, [])

        assert profile["favourite_films"] == ["Beta", "Alpha"]

    def test_ties_break_alphabetically_by_title(self):
        lib = library("u1", film("Zulu", 4.0), film("Alpha", 4.0))

        profile = _user_profile(lib, [])

        assert profile["favourite_films"] == ["Alpha", "Zulu"]

    def test_limits_genres_and_favourite_films(self):
        genres = {f"G{i}" for i in range(PROFILE_TOP_GENRES + 2)}
        films = [
            film(f"F{i}", 5.0 - i * 0.1, genres=genres)
            for i in range(PROFILE_TOP_FILMS + 2)
        ]

        profile = _user_profile(library("u1", *films), [])

        assert len(profile["top_genres"]) == PROFILE_TOP_GENRES
        assert len(profile["favourite_films"]) == PROFILE_TOP_FILMS

    def test_empty_library(self):
        profile = _user_profile(library("u1"), [])

        assert profile == {
            "top_genres": [],
            "top_directors": [],
            "mean_rating": None,
            "mean_rating_on_shared_films": None,
            "favourite_films": [],
        }


class TestComputeMetricsExtra:
    def _same_films(self, ratings_a, ratings_b):
        names = [chr(65 + i) for i in range(len(ratings_a))]
        a = library("a", *(film(n, r) for n, r in zip(names, ratings_a)))
        b = library("b", *(film(n, r) for n, r in zip(names, ratings_b)))
        return a, b

    def test_empty_libraries_yield_no_score_or_ratios(self):
        result = compute_metrics(library("a"), library("b"), None, None)

        public = result.public
        assert public["compatibility_score"] is None
        assert public["overlap_ratio"] is None
        assert public["jaccard"] is None
        assert public["mean_rating_gap"] is None
        assert public["taste_similarity"] is None
        assert public["common_count"] == 0
        assert public["agreements"] == []
        assert public["divergences"] == []

    def test_user_ids_are_stringified_in_public_data(self):
        result = compute_metrics(
            library(1, film("A", 4.0)), library(2, film("B", 4.0)), None, None
        )

        assert result.public["library_sizes"] == {"1": 1, "2": 1}
        assert set(result.internal["profiles"]) == {"1", "2"}

    def test_score_uses_only_overlap_when_other_components_are_missing(self):
        a = library("a", film("A", None), film("B", None))
        b = library("b", film("A", None), film("B", None))

        result = compute_metrics(a, b, None, None)

        assert result.public["compatibility_score"] == 100

    def test_overlap_component_is_scaled_by_three(self):
        a = library("a", film("A", None), *(film(f"a{i}", None) for i in range(9)))
        b = library("b", film("A", None), *(film(f"b{i}", None) for i in range(9)))

        result = compute_metrics(a, b, None, None)

        assert result.public["overlap_ratio"] == 0.1
        assert result.public["compatibility_score"] == 30

    def test_overlap_component_is_capped_at_one(self):
        a = library("a", *(film(f"c{i}", None) for i in range(5)),
                    *(film(f"a{i}", None) for i in range(5)))
        b = library("b", *(film(f"c{i}", None) for i in range(5)),
                    *(film(f"b{i}", None) for i in range(5)))

        result = compute_metrics(a, b, None, None)

        assert result.public["overlap_ratio"] == 0.5
        assert result.public["compatibility_score"] == 100

    def test_negative_taste_similarity_is_clamped_to_zero_in_score(self):
        a = library("a", film("A", None))
        b = library("b", film("A", None))

        result = compute_metrics(
            a, b, np.array([1.0, 0.0]), np.array([-1.0, 0.0])
        )

        assert result.public["taste_similarity"] == -1.0
        # taste 0.4 * 0 + overlap 0.2 * 1, normalised by 0.6
        assert result.public["compatibility_score"] == 33

    def test_agreement_component_needs_enough_pairs(self):
        a, b = self._same_films([5.0, 5.0], [5.0, 5.0])

        result = compute_metrics(a, b, None, None)

        assert result.public["mean_rating_gap"] == 0.0
        # only overlap counts (agreement needs MIN_PAIRS_FOR_STATS pairs)
        assert result.public["compatibility_score"] == 100

    def test_maximum_rating_gap_zeroes_agreement_component(self):
        a, b = self._same_films([5.0, 5.0, 5.0], [0.5, 0.5, 0.5])

        result = compute_metrics(a, b, None, None)

        assert result.public["mean_rating_gap"] == 4.5
        # agreement 0.4 * 0 + overlap 0.2 * 1, normalised by 0.6
        assert result.public["compatibility_score"] == 33

    def test_perfect_agreement_gives_full_score(self):
        a, b = self._same_films([4.0, 3.0, 5.0], [4.0, 3.0, 5.0])

        result = compute_metrics(a, b, None, None)

        assert result.public["compatibility_score"] == 100

    def test_agreements_are_ranked_and_filtered(self):
        a = library(
            "a",
            film("Z", 5.0), film("A", 5.0), film("M", 4.5),
            film("L", 4.0), film("N", 3.5),
        )
        b = library(
            "b",
            film("Z", 5.0), film("A", 5.0), film("M", 4.5),
            film("L", 5.0), film("N", 5.0),
        )

        result = compute_metrics(a, b, None, None)

        assert [e["title"] for e in result.public["agreements"]] == ["A", "Z", "M", "L"]

    def test_agreements_are_limited_to_top_n(self):
        names = [f"F{i}" for i in range(TOP_N + 2)]
        a = library("a", *(film(n, 5.0) for n in names))
        b = library("b", *(film(n, 5.0) for n in names))

        result = compute_metrics(a, b, None, None)

        assert len(result.public["agreements"]) == TOP_N

    def test_divergences_respect_threshold_and_ordering(self):
        a = library(
            "a",
            film("B", 5.0), film("A", 5.0),
            film("C", 4.0), film("D", 4.0),
        )
        b = library(
            "b",
            film("B", 2.0), film("A", 2.0),
            film("C", 4.0 - DIVERGENCE_THRESHOLD),
            film("D", 4.0 - DIVERGENCE_THRESHOLD + 0.5),
        )

        result = compute_metrics(a, b, None, None)

        assert [e["title"] for e in result.public["divergences"]] == ["A", "B", "C"]

    def test_divergences_are_limited_to_top_n(self):
        names = [f"F{i}" for i in range(TOP_N + 2)]
        a = library("a", *(film(n, 5.0) for n in names))
        b = library("b", *(film(n, 1.0) for n in names))

        result = compute_metrics(a, b, None, None)

        assert len(result.public["divergences"]) == TOP_N

    def test_entry_movie_id_falls_back_to_second_library(self):
        a = library("a", film("A", 5.0, movie_id=None))
        b = library("b", film("A", 5.0, movie_id=7))

        result = compute_metrics(a, b, None, None)

        assert result.public["agreements"][0]["movie_id"] == "7"

    def test_entry_movie_id_prefers_first_library(self):
        a = library("a", film("A", 5.0, movie_id=3))
        b = library("b", film("A", 5.0, movie_id=7))

        result = compute_metrics(a, b, None, None)

        assert result.public["agreements"][0]["movie_id"] == "3"

    def test_entry_movie_id_is_none_when_neither_library_has_one(self):
        a = library("a", film("A", 5.0))
        b = library("b", film("A", 5.0))

        result = compute_metrics(a, b, None, None)

        assert result.public["agreements"][0]["movie_id"] is None

    def test_profiles_use_each_users_own_shared_ratings(self):
        a, b = self._same_films([5.0, 3.0], [1.0, 2.0])

        result = compute_metrics(a, b, None, None)

        profiles = result.internal["profiles"]
        assert profiles["a"]["mean_rating_on_shared_films"] == 4.0
        assert profiles["b"]["mean_rating_on_shared_films"] == 1.5

    def test_jaccard_uses_union_of_libraries(self):
        a = library("a", film("A", None), film("B", None))
        b = library("b", film("B", None), film("C", None))

        result = compute_metrics(a, b, None, None)

        assert result.public["common_count"] == 1
        assert result.public["jaccard"] == round(1 / 3, 3)
        assert result.public["overlap_ratio"] == 0.5
