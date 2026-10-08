from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.comparisons.exceptions import (
    ComparisonNotFoundError,
    InsufficientDataError,
    NotComparisonMemberError,
)
from apps.comparisons.services.comparison import (
    FIT_VERSION,
    _get_comparison,
    get_comparison_result,
)
from apps.comparisons.services.metrics import METRICS_VERSION
from apps.comparisons.services.snapshot import UserLibrary
from apps.recommendations.services.joint_profile import DEFAULT_POOL_SIZE


class ComparisonResultServiceTests(TestCase):
    def _comparison(self, users):
        comparison = mock.Mock()

        comparison.pk = "comparison-1"
        comparison.session.users.all.return_value = users

        comparison.metrics_json = {}
        comparison.inputs_hash = ""

        # ComparisonResult works with real datetime values.
        generated_at = timezone.now()
        comparison.created_at = generated_at
        comparison.updated_at = generated_at
        comparison.generated_at = generated_at

        comparison.narratives.filter.return_value.first.return_value = None

        return comparison

    def test_get_comparison_raises_when_missing(self):
        with mock.patch(
            "apps.comparisons.services.comparison.Comparison.objects"
        ) as objects:
            objects.prefetch_related.return_value.get.side_effect = (
                Exception("not found")
            )

            with self.assertRaises(Exception):
                _get_comparison(
                    mock.Mock(pk="user-1"),
                    "comparison-1",
                )

    def test_get_comparison_raises_when_validation_fails(self):
        with mock.patch(
            "apps.comparisons.services.comparison.Comparison.objects"
        ) as objects:
            objects.prefetch_related.return_value.get.side_effect = (
                ValidationError("invalid")
            )

            with self.assertRaises(ComparisonNotFoundError):
                _get_comparison(
                    mock.Mock(pk="user-1"),
                    "comparison-1",
                )

    def test_get_comparison_raises_when_value_is_invalid(self):
        with mock.patch(
            "apps.comparisons.services.comparison.Comparison.objects"
        ) as objects:
            objects.prefetch_related.return_value.get.side_effect = (
                ValueError("invalid")
            )

            with self.assertRaises(ComparisonNotFoundError):
                _get_comparison(
                    mock.Mock(pk="user-1"),
                    "comparison-1",
                )

    def test_get_comparison_raises_when_user_is_not_member(self):
        user = mock.Mock(pk="user-3")
        user_a = mock.Mock(pk="user-1")
        user_b = mock.Mock(pk="user-2")

        comparison = self._comparison([user_a, user_b])

        with mock.patch(
            "apps.comparisons.services.comparison.Comparison.objects"
        ) as objects:
            objects.prefetch_related.return_value.get.return_value = comparison

            with self.assertRaises(NotComparisonMemberError):
                _get_comparison(
                    user,
                    "comparison-1",
                )

    def test_get_comparison_returns_sorted_users(self):
        user_a = mock.Mock(pk="a")
        user_b = mock.Mock(pk="b")
        user = mock.Mock(pk="a")

        comparison = self._comparison([user_b, user_a])

        with mock.patch(
            "apps.comparisons.services.comparison.Comparison.objects"
        ) as objects:
            objects.prefetch_related.return_value.get.return_value = comparison

            result, users = _get_comparison(
                user,
                "comparison-1",
            )

        self.assertIs(result, comparison)
        self.assertEqual(
            [u.pk for u in users],
            ["a", "b"],
        )

    def test_get_comparison_result_requires_exactly_two_users(self):
        user = mock.Mock(pk="user-1")
        other = mock.Mock(pk="user-2")
        third = mock.Mock(pk="user-3")

        comparison = self._comparison(
            [user, other, third]
        )

        with mock.patch(
            "apps.comparisons.services.comparison._get_comparison",
            return_value=(
                comparison,
                [user, other, third],
            ),
        ):
            with self.assertRaises(InsufficientDataError):
                get_comparison_result(
                    user=user,
                    comparison_id="comparison-1",
                )

    def test_get_comparison_result_requires_ratings_for_both_users(self):
        user_a = mock.Mock(pk="user-1")
        user_b = mock.Mock(pk="user-2")

        comparison = self._comparison([user_a, user_b])

        libraries = [
            UserLibrary(
                user_id=user_a.pk,
                films={},
            ),
            UserLibrary(
                user_id=user_b.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
        ]

        with mock.patch(
            "apps.comparisons.services.comparison._get_comparison",
            return_value=(comparison, [user_a, user_b]),
        ), mock.patch(
            "apps.comparisons.services.comparison.load_library",
            side_effect=libraries,
        ), mock.patch(
            "apps.comparisons.services.comparison.compute_inputs_hash",
            return_value="hash",
        ):
            with self.assertRaises(InsufficientDataError):
                get_comparison_result(
                    user=user_a,
                    comparison_id="comparison-1",
                )

    def test_get_comparison_result_recomputes_metrics_when_hash_changes(
        self,
    ):
        user_a = mock.Mock(pk="user-1")
        user_b = mock.Mock(pk="user-2")

        comparison = self._comparison([user_a, user_b])
        comparison.inputs_hash = "old-hash"
        comparison.metrics_json = {
            "version": METRICS_VERSION,
            "public": {"old": True},
            "internal": {"old": True},
        }

        libraries = [
            UserLibrary(
                user_id=user_a.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
            UserLibrary(
                user_id=user_b.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
        ]

        computed = SimpleNamespace(
            public={"new": True},
            internal={"internal": True},
        )

        profiles = [
            mock.Mock(),
            mock.Mock(),
        ]

        cached = mock.Mock()
        cached.narrative_summary = "cached"
        cached.recommendations = []
        cached.individual_summaries = {
            "user-1": "summary",
            "user-2": "summary",
        }

        with mock.patch(
            "apps.comparisons.services.comparison._get_comparison",
            return_value=(comparison, [user_a, user_b]),
        ), mock.patch(
            "apps.comparisons.services.comparison.load_library",
            side_effect=libraries,
        ), mock.patch(
            "apps.comparisons.services.comparison.compute_inputs_hash",
            return_value="new-hash",
        ), mock.patch(
            "apps.comparisons.services.comparison.user_taste_profiles",
            return_value=profiles,
        ) as mock_profiles, mock.patch(
            "apps.comparisons.services.comparison.compute_metrics",
            return_value=computed,
        ) as mock_metrics, mock.patch(
            "apps.comparisons.services.comparison.ComparisonNarrative"
        ) as mock_narrative:
            mock_narrative.objects.filter.return_value.first.return_value = (
                cached
            )

            result = get_comparison_result(
                user=user_a,
                comparison_id="comparison-1",
            )

        self.assertEqual(
            comparison.metrics_json,
            {
                "version": METRICS_VERSION,
                "public": {"new": True},
                "internal": {"internal": True},
            },
        )

        self.assertEqual(
            comparison.inputs_hash,
            "new-hash",
        )

        mock_profiles.assert_called_once_with(
            [user_a, user_b]
        )

        mock_metrics.assert_called_once_with(
            libraries[0],
            libraries[1],
            profiles[0],
            profiles[1],
        )

        self.assertEqual(
            result.narrative,
            "cached",
        )

    def test_get_comparison_result_returns_cached_narrative(self):
        user_a = mock.Mock(pk="user-1")
        user_b = mock.Mock(pk="user-2")

        comparison = self._comparison([user_a, user_b])
        comparison.inputs_hash = "hash"
        comparison.metrics_json = {
            "version": METRICS_VERSION,
            "public": {"score": 80},
            "internal": {"internal": True},
        }

        cached = mock.Mock()
        cached.narrative_summary = "Cached summary"
        cached.recommendations = [
            {
                "movie_id": 1,
                "fit_version": FIT_VERSION,
            },
        ]
        cached.individual_summaries = {
            "user-1": "summary",
            "user-2": "summary",
        }

        libraries = [
            UserLibrary(
                user_id=user_a.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
            UserLibrary(
                user_id=user_b.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
        ]

        with mock.patch(
            "apps.comparisons.services.comparison._get_comparison",
            return_value=(comparison, [user_a, user_b]),
        ), mock.patch(
            "apps.comparisons.services.comparison.load_library",
            side_effect=libraries,
        ), mock.patch(
            "apps.comparisons.services.comparison.compute_inputs_hash",
            return_value="hash",
        ), mock.patch(
            "apps.comparisons.services.comparison.ComparisonNarrative"
        ) as mock_narrative, mock.patch(
            "apps.comparisons.services.comparison.find_joint_candidates"
        ) as mock_candidates, mock.patch(
            "apps.comparisons.services.comparison.ComparisonNarrativeClient"
        ) as mock_client:
            mock_narrative.objects.filter.return_value.first.return_value = (
                cached
            )

            result = get_comparison_result(
                user=user_a,
                comparison_id="comparison-1",
            )

        self.assertEqual(
            result.narrative,
            "Cached summary",
        )

        self.assertEqual(
            result.recommendations,
            [
                {
                    "movie_id": 1,
                    "fit_version": FIT_VERSION,
                },
            ],
        )

        self.assertTrue(
            result.narrative_available
        )

        mock_candidates.assert_not_called()
        mock_client.assert_not_called()

    def test_get_comparison_result_generates_and_caches_narrative(self):
        user_a = mock.Mock(pk="user-1")
        user_b = mock.Mock(pk="user-2")

        comparison = self._comparison([user_a, user_b])
        comparison.inputs_hash = "hash"
        comparison.metrics_json = {
            "version": METRICS_VERSION,
            "public": {
                "compatibility_score": 80,
            },
            "internal": {},
        }

        libraries = [
            UserLibrary(
                user_id=user_a.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
            UserLibrary(
                user_id=user_b.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
        ]

        movie = mock.Mock(
            pk=42,
            title="Dune",
            release_year=2021,
        )
        movie.genres.all.return_value = []

        candidate = SimpleNamespace(
            movie=movie,
            score=0.91234,
            per_user=[0.81, 0.93],
        )

        narrative_result = SimpleNamespace(
            summary="You both like science fiction.",
            reasons={
                1: "Strong match for both users.",
            },
            individual={},
        )

        client = mock.Mock()
        client.model = "test-model"
        client.generate.return_value = narrative_result

        with mock.patch(
            "apps.comparisons.services.comparison._get_comparison",
            return_value=(comparison, [user_a, user_b]),
        ), mock.patch(
            "apps.comparisons.services.comparison.load_library",
            side_effect=libraries,
        ), mock.patch(
            "apps.comparisons.services.comparison.compute_inputs_hash",
            return_value="hash",
        ), mock.patch(
            "apps.comparisons.services.comparison.user_taste_profiles",
            return_value=["profile-a", "profile-b"],
        ), mock.patch(
            "apps.comparisons.services.comparison.find_joint_candidates",
            return_value=[candidate],
        ), mock.patch(
            "apps.comparisons.services.comparison.calibrate_fits",
            return_value=[candidate],
        ), mock.patch(
            "apps.comparisons.services.comparison.ComparisonNarrativeClient",
            return_value=client,
        ), mock.patch(
            "apps.comparisons.services.comparison.ComparisonNarrative"
        ) as mock_narrative:
            mock_narrative.objects.filter.return_value.first.return_value = (
                None
            )
            mock_narrative.objects.update_or_create.return_value = mock.Mock()

            result = get_comparison_result(
                user=user_a,
                comparison_id="comparison-1",
            )

        self.assertEqual(
            result.narrative,
            "You both like science fiction.",
        )

        self.assertEqual(
            result.recommendations,
            [
                {
                    "movie_id": 42,
                    "title": "Dune",
                    "release_year": 2021,
                    "genres": [],
                    "score": 0.912,
                    "fit_version": FIT_VERSION,
                    "per_user": {
                        "user-1": 0.81,
                        "user-2": 0.93,
                    },
                    "justification": "Strong match for both users.",
                }
            ],
        )

        self.assertTrue(
            result.narrative_available
        )

        client.generate.assert_called_once()
        mock_narrative.objects.update_or_create.assert_called_once()

    def test_get_comparison_result_returns_fallback_when_narrative_fails(
        self,
    ):
        user_a = mock.Mock(pk="user-1")
        user_b = mock.Mock(pk="user-2")

        comparison = self._comparison([user_a, user_b])
        comparison.inputs_hash = "hash"
        comparison.metrics_json = {
            "version": METRICS_VERSION,
            "public": {"score": 80},
            "internal": {},
        }

        libraries = [
            UserLibrary(
                user_id=user_a.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
            UserLibrary(
                user_id=user_b.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
        ]

        movie = mock.Mock(
            pk=10,
            title="Dune",
            release_year=2021,
        )
        movie.genres.all.return_value = []

        candidate = SimpleNamespace(
            movie=movie,
            score=0.8,
            per_user=[0.7, 0.9],
        )

        client = mock.Mock()
        client.generate.return_value = None

        with mock.patch(
            "apps.comparisons.services.comparison._get_comparison",
            return_value=(comparison, [user_a, user_b]),
        ), mock.patch(
            "apps.comparisons.services.comparison.load_library",
            side_effect=libraries,
        ), mock.patch(
            "apps.comparisons.services.comparison.compute_inputs_hash",
            return_value="hash",
        ), mock.patch(
            "apps.comparisons.services.comparison.user_taste_profiles",
            return_value=["a", "b"],
        ), mock.patch(
            "apps.comparisons.services.comparison.find_joint_candidates",
            return_value=[candidate],
        ), mock.patch(
            "apps.comparisons.services.comparison.calibrate_fits",
            return_value=[candidate],
        ), mock.patch(
            "apps.comparisons.services.comparison.ComparisonNarrativeClient",
            return_value=client,
        ), mock.patch(
            "apps.comparisons.services.comparison.ComparisonNarrative"
        ) as mock_narrative:
            mock_narrative.objects.filter.return_value.first.return_value = (
                None
            )

            result = get_comparison_result(
                user=user_a,
                comparison_id="comparison-1",
            )

        self.assertEqual(
            result.narrative,
            "",
        )

        self.assertEqual(
            result.recommendations[0]["justification"],
            "",
        )

        self.assertFalse(
            result.narrative_available
        )

        mock_narrative.objects.update_or_create.assert_not_called()

    def test_get_comparison_result_reuses_profiles_after_metric_recalculation(
        self,
    ):
        user_a = mock.Mock(pk="user-1")
        user_b = mock.Mock(pk="user-2")

        comparison = self._comparison([user_a, user_b])
        comparison.inputs_hash = "old"
        comparison.metrics_json = {
            "version": METRICS_VERSION,
            "public": {"old": True},
            "internal": {},
        }

        libraries = [
            UserLibrary(
                user_id=user_a.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
            UserLibrary(
                user_id=user_b.pk,
                films={
                    ("dune", 2021): mock.Mock(),
                },
            ),
        ]

        profiles = [
            mock.Mock(name="profile-a"),
            mock.Mock(name="profile-b"),
        ]

        computed = SimpleNamespace(
            public={"new": True},
            internal={},
        )

        candidate = mock.Mock()
        candidate.movie.pk = 1
        candidate.movie.title = "Dune"
        candidate.movie.release_year = 2021
        candidate.movie.genres.all.return_value = []
        candidate.score = 0.9
        candidate.per_user = [0.8, 0.9]

        client = mock.Mock()
        client.generate.return_value = None

        with mock.patch(
            "apps.comparisons.services.comparison._get_comparison",
            return_value=(comparison, [user_a, user_b]),
        ), mock.patch(
            "apps.comparisons.services.comparison.load_library",
            side_effect=libraries,
        ), mock.patch(
            "apps.comparisons.services.comparison.compute_inputs_hash",
            return_value="new",
        ), mock.patch(
            "apps.comparisons.services.comparison.user_taste_profiles",
            return_value=profiles,
        ) as mock_profiles, mock.patch(
            "apps.comparisons.services.comparison.compute_metrics",
            return_value=computed,
        ) as mock_metrics, mock.patch(
            "apps.comparisons.services.comparison.find_joint_candidates",
            return_value=[candidate],
        ) as mock_candidates, mock.patch(
            "apps.comparisons.services.comparison.calibrate_fits",
            return_value=[candidate],
        ), mock.patch(
            "apps.comparisons.services.comparison.ComparisonNarrativeClient",
            return_value=client,
        ), mock.patch(
            "apps.comparisons.services.comparison.ComparisonNarrative"
        ) as mock_narrative:
            mock_narrative.objects.filter.return_value.first.return_value = (
                None
            )

            result = get_comparison_result(
                user=user_a,
                comparison_id="comparison-1",
            )

        self.assertEqual(
            result.narrative,
            "",
        )

        mock_profiles.assert_called_once_with(
            [user_a, user_b]
        )

        mock_metrics.assert_called_once_with(
            libraries[0],
            libraries[1],
            profiles[0],
            profiles[1],
        )

        mock_candidates.assert_called_once_with(
            users=[user_a, user_b],
            profiles=profiles,
            limit=DEFAULT_POOL_SIZE,
        )
