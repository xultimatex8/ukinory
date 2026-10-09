from __future__ import annotations

import numpy as np
from django.test import TestCase

from apps.comparisons.services.metrics import (
    HIGH_RATING,
    TOP_N,
    _favourites_counter,
    _mean,
    _pearson,
    _round,
    _top_shared,
    compute_metrics,
    cosine_similarity,
)
from apps.comparisons.services.snapshot import RatedFilm, UserLibrary


class MetricsHelpersTests(TestCase):
    def test_mean_returns_average(self):
        self.assertEqual(_mean([2.0, 4.0, 6.0]), 4.0)

    def test_mean_returns_none_for_empty_list(self):
        self.assertIsNone(_mean([]))

    def test_pearson_returns_none_with_insufficient_pairs(self):
        xs = [1.0, 2.0]
        ys = [1.0, 2.0]

        self.assertIsNone(_pearson(xs, ys))

    def test_pearson_returns_one_for_perfect_positive_correlation(self):
        xs = [1.0, 2.0, 3.0]
        ys = [2.0, 4.0, 6.0]

        self.assertAlmostEqual(_pearson(xs, ys), 1.0)

    def test_pearson_returns_minus_one_for_perfect_negative_correlation(self):
        xs = [1.0, 2.0, 3.0]
        ys = [6.0, 4.0, 2.0]

        self.assertAlmostEqual(_pearson(xs, ys), -1.0)

    def test_pearson_returns_none_when_first_values_are_constant(self):
        xs = [4.0, 4.0, 4.0]
        ys = [1.0, 2.0, 3.0]

        self.assertIsNone(_pearson(xs, ys))

    def test_pearson_returns_none_when_second_values_are_constant(self):
        xs = [1.0, 2.0, 3.0]
        ys = [4.0, 4.0, 4.0]

        self.assertIsNone(_pearson(xs, ys))

    def test_cosine_similarity_returns_none_when_first_vector_is_none(self):
        result = cosine_similarity(
            None,
            np.array([1.0, 2.0]),
        )

        self.assertIsNone(result)

    def test_cosine_similarity_returns_none_when_second_vector_is_none(self):
        result = cosine_similarity(
            np.array([1.0, 2.0]),
            None,
        )

        self.assertIsNone(result)

    def test_cosine_similarity_returns_none_for_zero_vector(self):
        result = cosine_similarity(
            np.array([0.0, 0.0]),
            np.array([1.0, 2.0]),
        )

        self.assertIsNone(result)

    def test_cosine_similarity_returns_one_for_identical_vectors(self):
        result = cosine_similarity(
            np.array([1.0, 2.0]),
            np.array([1.0, 2.0]),
        )

        self.assertAlmostEqual(result, 1.0)

    def test_cosine_similarity_returns_zero_for_orthogonal_vectors(self):
        result = cosine_similarity(
            np.array([1.0, 0.0]),
            np.array([0.0, 1.0]),
        )

        self.assertAlmostEqual(result, 0.0)

    def test_cosine_similarity_returns_minus_one_for_opposite_vectors(self):
        result = cosine_similarity(
            np.array([1.0, 0.0]),
            np.array([-1.0, 0.0]),
        )

        self.assertAlmostEqual(result, -1.0)

    def test_round_returns_none_for_none(self):
        self.assertIsNone(_round(None))

    def test_round_rounds_value(self):
        self.assertEqual(_round(0.123456), 0.123)

    def test_round_uses_custom_digits(self):
        self.assertEqual(_round(0.123456, 2), 0.12)

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

        self.assertEqual(result["Drama"], 1)
        self.assertNotIn("Comedy", result)

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

        self.assertEqual(result["Drama"], 1)
        self.assertNotIn("Comedy", result)

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

        self.assertEqual(result["Drama"], 2)
        self.assertEqual(result["Thriller"], 1)
        self.assertEqual(result["Comedy"], 1)

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

        self.assertEqual(
            result,
            ["Drama", "Comedy"],
        )

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

        self.assertEqual(
            len(result),
            TOP_N,
        )


class ComputeMetricsTests(TestCase):
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

        self.assertEqual(
            result.public["library_sizes"],
            {
                "user-a": 1,
                "user-b": 1,
            },
        )

        self.assertEqual(
            result.public["common_count"],
            0,
        )

        self.assertEqual(
            result.public["overlap_ratio"],
            0.0,
        )

        self.assertEqual(
            result.public["jaccard"],
            0.0,
        )

        self.assertIsNone(
            result.public["mean_rating_gap"],
        )

        self.assertIsNone(
            result.public["rating_correlation"],
        )

        self.assertEqual(
            result.public["agreements"],
            [],
        )

        self.assertEqual(
            result.public["divergences"],
            [],
        )

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

        self.assertEqual(
            result.public["common_count"],
            2,
        )

        self.assertEqual(
            result.public["overlap_ratio"],
            0.667,
        )

        self.assertEqual(
            result.public["jaccard"],
            0.5,
        )

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

        self.assertEqual(
            result.public["mean_rating_gap"],
            1.0,
        )

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

        self.assertEqual(
            result.public["rating_correlation"],
            1.0,
        )

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

        self.assertIsNone(
            result.public["rating_correlation"],
        )

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

        self.assertEqual(
            result.public["mean_rating_gap"],
            1.0,
        )

        self.assertIsNone(
            result.public["rating_correlation"],
        )

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

        self.assertEqual(
            [item["title"] for item in result.public["agreements"]],
            ["Dune", "Alien"],
        )

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

        self.assertEqual(
            [item["title"] for item in result.public["divergences"]],
            ["Dune", "Barbie"],
        )

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

        self.assertEqual(
            result.public["agreements"],
            [
                {
                    "movie_id": None,
                    "title": "Dune",
                    "release_year": 2021,
                    "ratings": {
                        "user-a": 5.0,
                        "user-b": 4.0,
                    },
                }
            ],
        )

        self.assertEqual(
            result.public["divergences"],
            [],
        )

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

        self.assertEqual(
            result.public["taste_similarity"],
            1.0,
        )

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

        self.assertIsNone(
            result.public["taste_similarity"],
        )

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

        self.assertIsNotNone(
            result.public["compatibility_score"],
        )

        self.assertGreaterEqual(
            result.public["compatibility_score"],
            0,
        )

        self.assertLessEqual(
            result.public["compatibility_score"],
            100,
        )

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

        self.assertEqual(
            result.internal["shared_genres"],
            ["Sci-Fi"],
        )

        self.assertEqual(
            result.internal["shared_directors"],
            ["Denis Villeneuve"],
        )

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

        self.assertIsInstance(
            result.public,
            dict,
        )

        self.assertIsInstance(
            result.internal,
            dict,
        )

        self.assertIn(
            "compatibility_score",
            result.public,
        )

        self.assertIn(
            "shared_genres",
            result.internal,
        )

        self.assertIn(
            "shared_directors",
            result.internal,
        )
