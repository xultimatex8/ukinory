from __future__ import annotations

import itertools
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from apps.library.models import Rating
from apps.movies.models import Movie
from apps.recommendations.dtos.candidate import JointCandidate
from apps.recommendations.services import joint_profile
from apps.recommendations.services.joint_profile import (
    _catalog_sample,
    _cos,
    _unit,
    build_joint_profile,
    calibrate_fits,
    find_joint_candidates,
    user_taste_profiles,
)

MODULE = "apps.recommendations.services.joint_profile"

DIMS = Movie._meta.get_field("embedding").dimensions
_tmdb_ids = itertools.count(940000)


def vec(*values):
    return [float(v) for v in values] + [0.0] * (DIMS - len(values))


def np_vec(*values):
    return np.array(vec(*values), dtype=np.float32)


def make_movie(title, embedding):
    return Movie.objects.create(
        tmdb_id=next(_tmdb_ids), title=title, release_year=2000, embedding=embedding
    )


def cosine(a, b):
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def joint_candidate(per_user, score=0.5, movie="film"):
    return JointCandidate(movie=movie, score=score, per_user=list(per_user))


class TestUnit:
    def test_normalises_to_length_one(self):
        result = _unit(np.array([3.0, 4.0]))

        np.testing.assert_allclose(result, [0.6, 0.8], rtol=1e-6)
        assert np.linalg.norm(result) == pytest.approx(1.0)

    def test_zero_vector_gives_none(self):
        assert _unit(np.zeros(3)) is None

    def test_result_is_float32(self):
        assert _unit(np.array([1.0, 1.0])).dtype == np.float32


class TestBuildJointProfile:
    def test_averages_the_unit_vectors(self):
        result = build_joint_profile([np.array([3.0, 0.0]), np.array([0.0, 4.0])])

        np.testing.assert_allclose(result, [0.5, 0.5])

    def test_scale_of_each_profile_does_not_matter(self):
        small = build_joint_profile([np.array([1.0, 0.0]), np.array([0.0, 1.0])])
        large = build_joint_profile([np.array([100.0, 0.0]), np.array([0.0, 0.1])])

        np.testing.assert_allclose(small, large, rtol=1e-6)

    def test_missing_profile_gives_none(self):
        assert build_joint_profile([np.array([1.0, 0.0]), None]) is None

    def test_zero_profile_gives_none(self):
        assert build_joint_profile([np.array([1.0, 0.0]), np.zeros(2)]) is None

    def test_no_profiles_gives_none(self):
        assert build_joint_profile([]) is None

    def test_single_profile_gives_its_direction(self):
        result = build_joint_profile([np.array([0.0, 5.0])])

        np.testing.assert_allclose(result, [0.0, 1.0])

    def test_result_is_float32(self):
        result = build_joint_profile([np.array([1.0, 0.0]), np.array([0.0, 1.0])])

        assert result.dtype == np.float32


class TestCos:
    def test_identical_vectors(self):
        assert _cos(np.array([1.0, 2.0]), np.array([2.0, 4.0])) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cos(np.array([1.0, 0.0]), np.array([0.0, 3.0])) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert _cos(np.array([1.0, 0.0]), np.array([-2.0, 0.0])) == pytest.approx(-1.0)


class TestUserTasteProfiles:
    def test_builds_one_profile_per_user_in_order(self):
        users = [SimpleNamespace(pk=1), SimpleNamespace(pk=2)]
        profiles = {1: np.array([1.0]), 2: None}

        with patch(
            f"{MODULE}.build_taste_profile", side_effect=lambda u: profiles[u.pk]
        ) as build:
            result = user_taste_profiles(users)

        assert result[0] is profiles[1]
        assert result[1] is None
        assert [c.args[0] for c in build.call_args_list] == users

    def test_no_users(self):
        assert user_taste_profiles([]) == []


class TestCalibrateFits:
    SAMPLE = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]], dtype=np.float32)
    PROFILES = [np.array([1.0, 0.0]), np.array([0.0, 1.0])]

    def test_empty_pool_is_returned_without_sampling(self):
        pool = []

        with patch(f"{MODULE}._catalog_sample") as sample:
            assert calibrate_fits(pool, self.PROFILES) is pool

        sample.assert_not_called()

    def test_pool_is_unchanged_without_a_catalog_sample(self):
        pool = [joint_candidate([0.8, 0.2])]

        with patch(f"{MODULE}._catalog_sample", return_value=None):
            assert calibrate_fits(pool, self.PROFILES) is pool

    @pytest.mark.parametrize(
        "profiles", [[np.array([1.0, 0.0]), None], [np.array([1.0, 0.0]), np.zeros(2)]]
    )
    def test_pool_is_unchanged_when_a_profile_is_unusable(self, profiles):
        pool = [joint_candidate([0.8, 0.2])]

        with patch(f"{MODULE}._catalog_sample", return_value=self.SAMPLE):
            assert calibrate_fits(pool, profiles) is pool

    def test_fits_are_stretched_between_catalog_median_and_pool_best(self):
        pool = [joint_candidate([0.8, 0.2]), joint_candidate([0.4, 0.6])]

        with patch(f"{MODULE}._catalog_sample", return_value=self.SAMPLE):
            result = calibrate_fits(pool, self.PROFILES)

        # catalog medians are 0 for both users; pool bests are 0.8 and 0.6
        assert result[0].per_user == pytest.approx([1.0, 0.2 / 0.6])
        assert result[1].per_user == pytest.approx([0.5, 1.0])

    def test_movie_and_score_are_preserved(self):
        pool = [joint_candidate([0.8, 0.2], score=0.42, movie="Dune")]

        with patch(f"{MODULE}._catalog_sample", return_value=self.SAMPLE):
            result = calibrate_fits(pool, self.PROFILES)

        assert result[0].movie == "Dune"
        assert result[0].score == 0.42

    def test_the_original_pool_is_not_modified(self):
        pool = [joint_candidate([0.8, 0.2])]

        with patch(f"{MODULE}._catalog_sample", return_value=self.SAMPLE):
            calibrate_fits(pool, self.PROFILES)

        assert pool[0].per_user == [0.8, 0.2]

    def test_fits_below_the_catalog_median_are_clipped_to_zero(self):
        pool = [joint_candidate([0.8, 0.6]), joint_candidate([-0.5, -0.5])]

        with patch(f"{MODULE}._catalog_sample", return_value=self.SAMPLE):
            result = calibrate_fits(pool, self.PROFILES)

        assert result[1].per_user == [0.0, 0.0]

    def test_a_user_whose_candidates_are_all_at_the_median_gets_zero_fit(self):
        pool = [joint_candidate([0.0, 0.5]), joint_candidate([0.0, 0.3])]

        with patch(f"{MODULE}._catalog_sample", return_value=self.SAMPLE):
            result = calibrate_fits(pool, self.PROFILES)

        assert [c.per_user[0] for c in result] == [0.0, 0.0]
        assert result[0].per_user[1] == pytest.approx(1.0)

    def test_all_fits_are_between_zero_and_one(self):
        pool = [joint_candidate([0.9, -0.2]), joint_candidate([0.1, 0.7])]

        with patch(f"{MODULE}._catalog_sample", return_value=self.SAMPLE):
            result = calibrate_fits(pool, self.PROFILES)

        assert all(0.0 <= fit <= 1.0 for c in result for fit in c.per_user)


@pytest.mark.django_db
class TestCatalogSample:
    def test_too_small_a_catalog_gives_none(self):
        make_movie("Only one", vec(1, 0))

        assert _catalog_sample() is None

    def test_rows_are_unit_vectors(self, monkeypatch):
        monkeypatch.setattr(joint_profile, "CALIBRATION_MIN_SAMPLE", 2)
        make_movie("A", vec(3, 0))
        make_movie("B", vec(0, 4))

        sample = _catalog_sample()

        assert sample.shape == (2, DIMS)
        np.testing.assert_allclose(np.linalg.norm(sample, axis=1), [1.0, 1.0], rtol=1e-5)

    def test_zero_vectors_stay_zero_instead_of_becoming_nan(self, monkeypatch):
        monkeypatch.setattr(joint_profile, "CALIBRATION_MIN_SAMPLE", 2)
        make_movie("Zero", vec(0, 0))
        make_movie("A", vec(1, 0))

        sample = _catalog_sample()

        assert not np.isnan(sample).any()

    def test_films_without_embedding_do_not_count(self, monkeypatch):
        monkeypatch.setattr(joint_profile, "CALIBRATION_MIN_SAMPLE", 2)
        make_movie("A", vec(1, 0))
        make_movie("No embedding", None)

        assert _catalog_sample() is None

    def test_sample_size_is_capped(self, monkeypatch):
        monkeypatch.setattr(joint_profile, "CALIBRATION_MIN_SAMPLE", 2)
        monkeypatch.setattr(joint_profile, "CALIBRATION_SAMPLE_SIZE", 3)
        for n in range(5):
            make_movie(f"Film {n}", vec(1, n))

        assert _catalog_sample().shape[0] == 3


@pytest.mark.django_db
class TestFindJointCandidates:
    def _profiles(self):
        return [np_vec(1, 0), np_vec(0, 1)]

    def _catalog(self):
        both = make_movie("Both", vec(1, 1))
        leans_a = make_movie("Leans A", vec(1, 0.1))
        leans_b = make_movie("Leans B", vec(0.1, 1))
        far = make_movie("Far", vec(-1, -1))
        return both, leans_a, leans_b, far

    def test_best_for_both_users_comes_first(self, user, another_user):
        both, *_ = self._catalog()

        result = find_joint_candidates(
            users=[user, another_user], profiles=self._profiles()
        )

        assert result[0].movie.pk == both.pk

    def test_candidates_are_sorted_by_score_descending(self, user, another_user):
        self._catalog()

        result = find_joint_candidates(
            users=[user, another_user], profiles=self._profiles()
        )

        scores = [c.score for c in result]
        assert scores == sorted(scores, reverse=True)

    def test_per_user_similarities_follow_the_profile_order(self, user, another_user):
        _, leans_a, *_ = self._catalog()

        result = find_joint_candidates(
            users=[user, another_user], profiles=self._profiles()
        )

        candidate = next(c for c in result if c.movie.pk == leans_a.pk)
        expected = [cosine(vec(1, 0.1), vec(1, 0)), cosine(vec(1, 0.1), vec(0, 1))]
        assert candidate.per_user == pytest.approx(expected, rel=1e-4)
        assert candidate.per_user[0] > candidate.per_user[1]

    @pytest.mark.parametrize("weight", [0.0, 0.5, 1.0])
    def test_score_blends_mean_and_least_happy_user(self, user, another_user, weight):
        _, leans_a, *_ = self._catalog()

        result = find_joint_candidates(
            users=[user, another_user],
            profiles=self._profiles(),
            least_misery_weight=weight,
        )

        candidate = next(c for c in result if c.movie.pk == leans_a.pk)
        sims = candidate.per_user
        expected = (1 - weight) * (sum(sims) / len(sims)) + weight * min(sims)
        assert candidate.score == pytest.approx(expected, rel=1e-4)

    def test_limit_caps_the_results(self, user, another_user):
        self._catalog()

        result = find_joint_candidates(
            users=[user, another_user], profiles=self._profiles(), limit=2
        )

        assert len(result) == 2

    def test_pool_size_restricts_the_shortlist_to_the_nearest_films(
        self, user, another_user
    ):
        both, *_ = self._catalog()

        result = find_joint_candidates(
            users=[user, another_user], profiles=self._profiles(), pool_size=1
        )

        assert [c.movie.pk for c in result] == [both.pk]

    def test_films_rated_by_any_of_the_users_are_excluded(self, user, another_user):
        both, leans_a, leans_b, _ = self._catalog()
        Rating.objects.create(
            user=user, title=both.title, release_year=2000, movie=both,
            rating=4.0, liked=False,
        )
        Rating.objects.create(
            user=another_user, title=leans_a.title, release_year=2000, movie=leans_a,
            rating=4.0, liked=False,
        )

        result = find_joint_candidates(
            users=[user, another_user], profiles=self._profiles()
        )

        returned = {c.movie.pk for c in result}
        assert both.pk not in returned and leans_a.pk not in returned
        assert leans_b.pk in returned

    def test_other_users_ratings_do_not_exclude_films(self, user, another_user, other_user):
        both, *_ = self._catalog()
        Rating.objects.create(
            user=other_user, title=both.title, release_year=2000, movie=both,
            rating=4.0, liked=False,
        )

        result = find_joint_candidates(
            users=[user, another_user], profiles=self._profiles()
        )

        assert both.pk in {c.movie.pk for c in result}

    def test_explicitly_excluded_films_are_skipped(self, user, another_user):
        both, *_ = self._catalog()

        result = find_joint_candidates(
            users=[user, another_user],
            profiles=self._profiles(),
            exclude_movie_ids=[both.pk],
        )

        assert both.pk not in {c.movie.pk for c in result}

    def test_films_without_embedding_are_never_returned(self, user, another_user):
        no_embedding = make_movie("No embedding", None)
        self._catalog()

        result = find_joint_candidates(
            users=[user, another_user], profiles=self._profiles()
        )

        assert no_embedding.pk not in {c.movie.pk for c in result}

    @pytest.mark.parametrize(
        "profiles", [[None, np_vec(0, 1)], [np_vec(1, 0), None], [np_vec(1, 0), np_vec(0, 0)]]
    )
    def test_unusable_profiles_give_no_candidates(self, user, another_user, profiles):
        self._catalog()

        assert find_joint_candidates(users=[user, another_user], profiles=profiles) == []

    def test_profiles_are_built_from_the_users_when_not_given(self, user, another_user):
        both, *_ = self._catalog()
        profiles = {user.pk: np_vec(1, 0), another_user.pk: np_vec(0, 1)}

        with patch(
            f"{MODULE}.build_taste_profile", side_effect=lambda u: profiles[u.pk]
        ):
            result = find_joint_candidates(users=[user, another_user])

        assert result[0].movie.pk == both.pk
