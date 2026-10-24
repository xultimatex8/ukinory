from __future__ import annotations

import copy
import uuid
from contextlib import ExitStack
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.common.enums import SessionType
from apps.comparisons.exceptions import ComparisonNotFoundError, InsufficientDataError
from apps.comparisons.models import Comparison, ComparisonSession
from apps.comparisons.services.comparison import (
    FIT_VERSION,
    _get_comparison,
    _json_safe,
    _serialize_candidates,
    attach_participants,
    attach_tmdb_metadata,
    get_comparison_result,
    list_comparisons,
)
from apps.comparisons.services.metrics import METRICS_VERSION
from apps.comparisons.services.snapshot import UserLibrary
from apps.recommendations.services.joint_profile import DEFAULT_POOL_SIZE
from apps.common.exceptions import NotSessionMemberError
from apps.movies.models import Movie
import pytest

User = get_user_model()
MODULE = "apps.comparisons.services.comparison"


@pytest.mark.django_db
class TestComparisonResultService:
    def _comparison(self, users):
        comparison = mock.Mock()

        comparison.pk = "comparison-1"
        comparison.session.users.all.return_value = users

        comparison.metrics_json = {}
        comparison.inputs_hash = ""

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

            with pytest.raises(Exception):
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

            with pytest.raises(ComparisonNotFoundError):
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

            with pytest.raises(ComparisonNotFoundError):
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

            with pytest.raises(NotSessionMemberError):
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

        assert result is comparison
        assert [u.pk for u in users] == ["a", "b"]

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
            with pytest.raises(InsufficientDataError):
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
            with pytest.raises(InsufficientDataError):
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

        assert comparison.metrics_json == {
            "version": METRICS_VERSION,
            "public": {"new": True},
            "internal": {"internal": True},
        }

        assert comparison.inputs_hash == "new-hash"

        mock_profiles.assert_called_once_with(
            [user_a, user_b]
        )

        mock_metrics.assert_called_once_with(
            libraries[0],
            libraries[1],
            profiles[0],
            profiles[1],
        )

        assert result.narrative == "cached"

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

        assert result.narrative == "Cached summary"

        assert result.recommendations == [
            {
                "movie_id": 1,
                "fit_version": FIT_VERSION,
            },
        ]

        assert result.narrative_available

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

        assert result.narrative == "You both like science fiction."

        assert result.recommendations == [
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
        ]

        assert result.narrative_available

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

        assert result.narrative == ""

        assert result.recommendations[0]["justification"] == ""

        assert not result.narrative_available

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

        assert result.narrative == ""

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


class TestJsonSafe:
    def test_converts_uuid_date_decimal_and_datetime(self):
        uid = uuid.uuid4()

        result = _json_safe(
            {
                "id": uid,
                "day": date(2024, 1, 2),
                "price": Decimal("1.5"),
                "at": datetime(2024, 1, 2, 3, 4, 5, tzinfo=dt_timezone.utc),
            }
        )

        assert result == {
            "id": str(uid),
            "day": "2024-01-02",
            "price": "1.5",
            "at": "2024-01-02T03:04:05Z",
        }

    def test_turns_tuples_into_lists_and_handles_nesting(self):
        assert _json_safe({"a": (1, 2), "b": [{"c": (3,)}]}) == {"a": [1, 2], "b": [{"c": [3]}]}

    def test_leaves_plain_values_untouched(self):
        value = {"a": 1, "b": "x", "c": None, "d": [1.5, True]}

        assert _json_safe(value) == value


@pytest.mark.django_db
class TestListComparisons:
    def _comparison(self, *users):
        room = ComparisonSession.objects.create(
            session_type=SessionType.COMPARISON_SESSION
        )
        room.users.add(*users)
        return Comparison.objects.create(session=room)

    def test_returns_only_comparisons_of_the_users_sessions(
        self, user, another_user, other_user
    ):
        first = self._comparison(user, another_user)
        second = self._comparison(another_user, other_user)

        assert {c.pk for c in list_comparisons(user)} == {first.pk}
        assert {c.pk for c in list_comparisons(other_user)} == {second.pk}
        assert {c.pk for c in list_comparisons(another_user)} == {first.pk, second.pk}

    def test_returns_nothing_for_user_without_sessions(
        self, user, another_user, other_user
    ):
        self._comparison(user, another_user)

        assert list(list_comparisons(other_user)) == []

    def test_does_not_duplicate_comparisons(self, user, another_user):
        self._comparison(user, another_user)

        assert len(list(list_comparisons(user))) == 1


class TestSerializeCandidates:
    def _candidate(self, pk=42, title="Dune", score=0.91234, per_user=(0.81234, 0.9)):
        movie = mock.Mock(pk=pk, title=title, release_year=2021)
        movie.genres.all.return_value = [
            SimpleNamespace(name="Sci-Fi"),
            SimpleNamespace(name="Adventure"),
        ]
        return SimpleNamespace(
            movie=movie, score=score, per_user=list(per_user)
        )

    def test_serializes_candidate_fields(self):
        result = _serialize_candidates(
            [self._candidate()], {1: "Why"}, ["u1", "u2"]
        )

        assert result == [
            {
                "movie_id": 42,
                "title": "Dune",
                "release_year": 2021,
                "genres": ["Sci-Fi", "Adventure"],
                "score": 0.912,
                "fit_version": FIT_VERSION,
                "per_user": {"u1": 0.812, "u2": 0.9},
                "justification": "Why",
            }
        ]

    def test_reasons_are_matched_by_one_based_position(self):
        result = _serialize_candidates(
            [self._candidate(pk=1), self._candidate(pk=2)],
            {2: "second"},
            ["u1", "u2"],
        )

        assert result[0]["justification"] == ""
        assert result[1]["justification"] == "second"

    def test_empty_candidates_return_empty_list(self):
        assert _serialize_candidates([], {}, ["u1", "u2"]) == []

    def test_output_is_json_safe(self):
        uid = uuid.uuid4()

        result = _serialize_candidates(
            [self._candidate(pk=uid)], {}, ["u1", "u2"]
        )

        assert result[0]["movie_id"] == str(uid)


@pytest.mark.django_db
class TestAttachTmdbMetadata:
    @pytest.fixture(autouse=True)
    def _movies(self, db):
        self.dune = Movie.objects.create(
            tmdb_id=3001, title="Dune", release_year=2020
        )
        self.alien = Movie.objects.create(
            tmdb_id=3002, title="Alien", release_year=1978
        )
        self.heat = Movie.objects.create(
            tmdb_id=3003, title="Heat", release_year=1994
        )

    def _payload(self):
        return {
            "metrics": {
                "compatibility_score": 80,
                "agreements": [
                    {
                        "movie_id": str(self.dune.pk),
                        "title": "Dune",
                        "release_year": 2020,
                    }
                ],
                "divergences": [
                    {
                        "movie_id": str(self.alien.pk),
                        "title": "Alien",
                        "release_year": 1978,
                    }
                ],
            },
            "recommendations": [
                {
                    "movie_id": str(self.heat.pk),
                    "title": "Heat",
                    "release_year": 1994,
                    "genres": ["Crime"],
                }
            ],
        }

    def _meta(self, title, year, poster, genres):
        return {
            "title": title,
            "release_year": year,
            "poster_url": poster,
            "genres": genres,
        }

    def _attach(self, payload, metadata):
        with mock.patch(
            f"{MODULE}.fetch_card_metadata_bulk", return_value=metadata
        ) as fetch:
            result = attach_tmdb_metadata(payload)
        return result, fetch

    def test_returns_payload_unchanged_without_movie_ids(self):
        payload = {"metrics": {}, "recommendations": []}

        result, fetch = self._attach(payload, {})

        assert result is payload
        fetch.assert_not_called()

    def test_ignores_entries_without_movie_id_when_collecting_ids(self):
        payload = {
            "metrics": {
                "agreements": [
                    {"movie_id": None, "title": "X", "release_year": None}
                ]
            }
        }

        result, fetch = self._attach(payload, {})

        assert result is payload
        fetch.assert_not_called()

    def test_requests_metadata_for_all_tmdb_ids_at_once(self):
        _, fetch = self._attach(self._payload(), {})

        fetch.assert_called_once_with({3001, 3002, 3003})

    def test_enriches_agreements_divergences_and_recommendations(self):
        metadata = {
            3001: self._meta("Dune (TMDB)", 2021, "http://p/dune.jpg", ["SF"]),
            3002: self._meta("Alien (TMDB)", 1979, "http://p/alien.jpg", ["H"]),
            3003: self._meta("Heat (TMDB)", 1995, "http://p/heat.jpg", ["C"]),
        }

        result, _ = self._attach(self._payload(), metadata)

        agreement = result["metrics"]["agreements"][0]
        assert agreement["title"] == "Dune (TMDB)"
        assert agreement["release_year"] == 2021
        assert agreement["poster_url"] == "http://p/dune.jpg"
        assert agreement["tmdb_id"] == 3001
        assert "genres" not in agreement

        divergence = result["metrics"]["divergences"][0]
        assert divergence["title"] == "Alien (TMDB)"
        assert divergence["tmdb_id"] == 3002

        recommendation = result["recommendations"][0]
        assert recommendation["title"] == "Heat (TMDB)"
        assert recommendation["genres"] == ["C"]
        assert recommendation["poster_url"] == "http://p/heat.jpg"

    def test_preserves_other_metrics(self):
        result, _ = self._attach(self._payload(), {})

        assert result["metrics"]["compatibility_score"] == 80

    def test_falls_back_to_local_values_when_metadata_is_blank(self):
        metadata = {3003: self._meta("", None, "http://p/heat.jpg", [])}

        result, _ = self._attach(self._payload(), metadata)

        recommendation = result["recommendations"][0]
        assert recommendation["title"] == "Heat"
        assert recommendation["release_year"] == 1994
        assert recommendation["genres"] == ["Crime"]
        assert recommendation["poster_url"] == "http://p/heat.jpg"

    def test_uses_empty_poster_when_tmdb_has_no_metadata(self):
        result, _ = self._attach(self._payload(), {})

        agreement = result["metrics"]["agreements"][0]
        assert agreement["poster_url"] == ""
        assert agreement["tmdb_id"] == 3001
        assert agreement["title"] == "Dune"

    def test_unknown_or_missing_movie_ids_get_no_tmdb_id(self):
        payload = self._payload()
        payload["recommendations"] = [
            {"movie_id": "00000000-0000-0000-0000-000000000000", "title": "Ghost", "release_year": 2000},
            {"movie_id": None, "title": "Nameless", "release_year": None},
        ]

        result, _ = self._attach(payload, {})

        for rec in result["recommendations"]:
            assert rec["tmdb_id"] is None
            assert rec["poster_url"] == ""

    def test_does_not_mutate_input_payload(self):
        payload = self._payload()
        original = copy.deepcopy(payload)

        self._attach(
            payload,
            {3001: self._meta("Other", 1999, "http://p/x.jpg", ["X"])},
        )

        assert payload == original

    def test_payload_without_recommendations_key_is_supported(self):
        payload = self._payload()
        del payload["recommendations"]

        result, _ = self._attach(payload, {})

        assert result["recommendations"] == []
        assert len(result["metrics"]["agreements"]) == 1


class TestAttachParticipants:
    def test_adds_participants_and_current_user(self):
        alice = SimpleNamespace(pk=1, username="alice")
        bob = SimpleNamespace(pk=2, username="bob")
        comparison = SimpleNamespace(
            session=SimpleNamespace(users=SimpleNamespace(all=lambda: [alice, bob]))
        )
        payload = {"metrics": {"x": 1}}

        result = attach_participants(payload, comparison, bob)

        assert result["participants"] == {"1": "alice", "2": "bob"}
        assert result["current_user_id"] == "2"
        assert result["metrics"] == {"x": 1}

    def test_does_not_mutate_input_payload(self):
        user = SimpleNamespace(pk=1, username="alice")
        comparison = SimpleNamespace(
            session=SimpleNamespace(users=SimpleNamespace(all=lambda: [user]))
        )
        payload = {"metrics": {}}

        attach_participants(payload, comparison, user)

        assert payload == {"metrics": {}}


@pytest.mark.django_db
class TestGetComparisonResultCaching:
    """Cache / recompute decisions of get_comparison_result."""

    @pytest.fixture(autouse=True)
    def _users(self):
        self.users = [mock.Mock(pk="user-1"), mock.Mock(pk="user-2")]

    def _comparison(self, *, inputs_hash="hash", metrics_json=None):
        comparison = mock.Mock()
        comparison.pk = "comparison-1"
        comparison.inputs_hash = inputs_hash
        comparison.metrics_json = (
            {"version": METRICS_VERSION, "public": {}, "internal": {}}
            if metrics_json is None
            else metrics_json
        )
        return comparison

    def _generated(self):
        return SimpleNamespace(
            summary="fresh",
            reasons={},
            individual={"user-1": "a", "user-2": "b"},
        )

    def _cached(self, *, recommendations=None, individual=None):
        return SimpleNamespace(
            narrative_summary="cached",
            recommendations=(
                [{"movie_id": 1, "fit_version": FIT_VERSION}]
                if recommendations is None
                else recommendations
            ),
            individual_summaries=(
                {"user-1": "a", "user-2": "b"}
                if individual is None
                else individual
            ),
        )

    def _run(self, comparison, *, cached=None, generated=None):
        libraries = [
            UserLibrary(user_id=u.pk, films={("dune", 2021): mock.Mock()})
            for u in self.users
        ]
        client = mock.Mock()
        client.model = "test-model"
        client.generate.return_value = generated

        patches = {
            "_get_comparison": {"return_value": (comparison, self.users)},
            "load_library": {"side_effect": libraries},
            "compute_inputs_hash": {"return_value": "hash"},
            "compute_metrics": {
                "return_value": SimpleNamespace(
                    public={"score": 1}, internal={"i": 1}
                )
            },
            "user_taste_profiles": {"return_value": ["pa", "pb"]},
            "find_joint_candidates": {"return_value": []},
            "calibrate_fits": {"return_value": []},
            "ComparisonNarrativeClient": {"return_value": client},
        }
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(mock.patch(f"{MODULE}.{name}", **kw))
                for name, kw in patches.items()
            }
            narrative_model = stack.enter_context(
                mock.patch(f"{MODULE}.ComparisonNarrative")
            )
            narrative_model.objects.filter.return_value.first.return_value = (
                cached
            )
            result = get_comparison_result(
                user=self.users[0], comparison_id="comparison-1"
            )
        return result, mocks, narrative_model, client

    def test_does_not_recompute_metrics_when_hash_and_version_match(self):
        comparison = self._comparison()

        _, mocks, _, _ = self._run(comparison, generated=self._generated())

        mocks["compute_metrics"].assert_not_called()
        comparison.save.assert_not_called()

    def test_recomputes_metrics_when_version_is_outdated(self):
        comparison = self._comparison(
            metrics_json={
                "version": METRICS_VERSION - 1,
                "public": {},
                "internal": {},
            }
        )

        _, mocks, _, _ = self._run(comparison, generated=self._generated())

        mocks["compute_metrics"].assert_called_once()
        comparison.save.assert_called_once_with(
            update_fields=["metrics_json", "inputs_hash", "generated_at"]
        )
        assert comparison.metrics_json["version"] == METRICS_VERSION
        assert comparison.metrics_json["public"] == {"score": 1}

    def test_recomputes_metrics_when_metrics_json_is_empty(self):
        comparison = self._comparison()
        comparison.metrics_json = {}

        _, mocks, _, _ = self._run(comparison, generated=self._generated())

        mocks["compute_metrics"].assert_called_once()

    def test_serves_cache_with_empty_recommendations(self):
        _, _, _, client = self._run(
            self._comparison(), cached=self._cached(recommendations=[])
        )

        client.generate.assert_not_called()

    def test_regenerates_when_cached_fit_version_is_outdated(self):
        cached = self._cached(
            recommendations=[{"movie_id": 1, "fit_version": FIT_VERSION - 1}]
        )

        result, _, _, client = self._run(
            self._comparison(), cached=cached, generated=self._generated()
        )

        client.generate.assert_called_once()
        assert result.narrative == "fresh"

    def test_regenerates_when_cached_has_no_individual_summaries(self):
        result, _, _, client = self._run(
            self._comparison(),
            cached=self._cached(individual={}),
            generated=self._generated(),
        )

        client.generate.assert_called_once()
        assert result.narrative == "fresh"

    def test_persists_generated_narrative_with_model_version(self):
        comparison = self._comparison()

        _, _, narrative_model, _ = self._run(
            comparison, generated=self._generated()
        )

        narrative_model.objects.update_or_create.assert_called_once()
        kwargs = narrative_model.objects.update_or_create.call_args.kwargs
        assert kwargs["comparison"] == comparison
        assert kwargs["inputs_hash"] == "hash"
        assert kwargs["defaults"] == {
            "narrative_summary": "fresh",
            "individual_summaries": {"user-1": "a", "user-2": "b"},
            "recommendations": [],
            "model_version": "test-model",
        }

    def test_deletes_narratives_from_older_inputs_after_generation(self):
        comparison = self._comparison()

        self._run(comparison, generated=self._generated())

        comparison.narratives.exclude.assert_called_once_with(
            inputs_hash="hash"
        )
        comparison.narratives.exclude.return_value.delete.assert_called_once_with()

    def test_does_not_persist_or_delete_when_generation_fails(self):
        comparison = self._comparison()

        result, _, narrative_model, _ = self._run(comparison, generated=None)

        narrative_model.objects.update_or_create.assert_not_called()
        comparison.narratives.exclude.assert_not_called()
        assert result.narrative == ""
        assert not result.narrative_available
