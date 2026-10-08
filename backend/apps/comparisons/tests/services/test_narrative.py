from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from apps.common.exceptions import QuotaExceeded
from apps.comparisons.services.narrative import (
    DEFAULT_MODEL,
    QUOTA_CLIENT_NAME,
    ComparisonNarrativeClient,
    _build_prompt,
    _compact_public,
    _labels,
    _parse,
)


class LabelsTests(TestCase):
    def test_labels_two_users(self):
        self.assertEqual(
            _labels(["10", "20"]),
            {
                "10": "A",
                "20": "B",
            },
        )

    def test_labels_multiple_users(self):
        self.assertEqual(
            _labels(["1", "2", "3"]),
            {
                "1": "A",
                "2": "B",
                "3": "C",
            },
        )


class CompactPublicTests(TestCase):
    def test_compacts_library_sizes(self):
        public = {
            "library_sizes": {
                "10": 100,
                "20": 80,
            },
            "agreements": [],
            "divergences": [],
        }

        result = _compact_public(
            public,
            _labels(["10", "20"]),
        )

        self.assertEqual(
            result["library_sizes"],
            {
                "A": 100,
                "B": 80,
            },
        )

    def test_compacts_ratings(self):
        public = {
            "library_sizes": {
                "10": 100,
                "20": 80,
            },
            "agreements": [
                {
                    "title": "Dune",
                    "release_year": 2021,
                    "ratings": {
                        "10": 5.0,
                        "20": 4.5,
                    },
                }
            ],
            "divergences": [
                {
                    "title": "Alien",
                    "release_year": 1979,
                    "ratings": {
                        "10": 2.0,
                        "20": 5.0,
                    },
                }
            ],
        }

        result = _compact_public(
            public,
            _labels(["10", "20"]),
        )

        self.assertEqual(
            result["agreements"][0]["ratings"],
            {
                "A": 5.0,
                "B": 4.5,
            },
        )

        self.assertEqual(
            result["divergences"][0]["ratings"],
            {
                "A": 2.0,
                "B": 5.0,
            },
        )

    def test_compacts_movie_metadata(self):
        public = {
            "compatibility_score": 85,
            "taste_similarity": 0.8,
            "common_count": 30,
            "mean_rating_gap": 0.5,
            "rating_correlation": 0.7,
            "library_sizes": {
                "10": 100,
                "20": 80,
            },
            "agreements": [
                {
                    "title": "Dune",
                    "release_year": 2021,
                    "ratings": {
                        "10": 5.0,
                        "20": 4.5,
                    },
                }
            ],
            "divergences": [],
        }

        result = _compact_public(
            public,
            _labels(["10", "20"]),
        )

        self.assertEqual(
            result["compatibility_score"],
            85,
        )

        self.assertEqual(
            result["taste_similarity"],
            0.8,
        )

        self.assertEqual(
            result["common_films"],
            30,
        )

        self.assertEqual(
            result["mean_rating_gap"],
            0.5,
        )

        self.assertEqual(
            result["rating_correlation"],
            0.7,
        )

        self.assertEqual(
            result["agreements"][0]["title"],
            "Dune",
        )

        self.assertEqual(
            result["agreements"][0]["year"],
            2021,
        )

    def test_does_not_mutate_public(self):
        public = {
            "compatibility_score": 85,
            "taste_similarity": 0.8,
            "library_sizes": {
                "10": 100,
                "20": 80,
            },
            "common_count": 30,
            "mean_rating_gap": 0.5,
            "rating_correlation": 0.7,
            "agreements": [],
            "divergences": [],
        }

        original = {
            "compatibility_score": 85,
            "taste_similarity": 0.8,
            "library_sizes": {
                "10": 100,
                "20": 80,
            },
            "common_count": 30,
            "mean_rating_gap": 0.5,
            "rating_correlation": 0.7,
            "agreements": [],
            "divergences": [],
        }

        _compact_public(
            public,
            _labels(["10", "20"]),
        )

        self.assertEqual(
            public,
            original,
        )


class BuildPromptTests(TestCase):
    def _public(self):
        return {
            "compatibility_score": 85,
            "taste_similarity": 0.8,
            "library_sizes": {
                "10": 100,
                "20": 90,
            },
            "common_count": 30,
            "overlap_ratio": 0.333,
            "jaccard": 0.2,
            "mean_rating_gap": 0.5,
            "rating_correlation": 0.7,
            "agreements": [],
            "divergences": [],
        }

    def _movie(self):
        movie = mock.Mock()
        movie.title = "Dune"
        movie.release_year = 2021
        movie.wikidata_description = "A science-fiction epic."

        genre_a = mock.Mock()
        genre_a.name = "Science Fiction"

        genre_b = mock.Mock()
        genre_b.name = "Drama"

        movie.genres.all.return_value = [
            genre_a,
            genre_b,
        ]

        return movie

    def _candidate(self):
        candidate = mock.Mock()
        candidate.movie = self._movie()
        candidate.per_user = [0.91, 0.84]
        return candidate

    def test_prompt_contains_metrics(self):
        prompt = _build_prompt(
            self._public(),
            {
                "shared_genres": ["Science Fiction"],
                "shared_directors": ["Denis Villeneuve"],
            },
            [],
            ["10", "20"],
        )

        self.assertIn(
            "Metrics:",
            prompt,
        )

        self.assertIn(
            "compatibility_score",
            prompt,
        )

        self.assertIn(
            "A",
            prompt,
        )

        self.assertIn(
            "B",
            prompt,
        )

    def test_prompt_contains_candidate_information(self):
        prompt = _build_prompt(
            self._public(),
            {
                "shared_genres": ["Science Fiction"],
                "shared_directors": ["Denis Villeneuve"],
            },
            [self._candidate()],
            ["10", "20"],
        )

        self.assertIn(
            "Dune",
            prompt,
        )

        self.assertIn(
            "2021",
            prompt,
        )

        self.assertIn(
            "Science Fiction",
            prompt,
        )

        self.assertIn(
            "fit A=0.91 B=0.84",
            prompt,
        )

        self.assertIn(
            "A science-fiction epic.",
            prompt,
        )

    def test_prompt_contains_individual_profiles(self):
        prompt = _build_prompt(
            self._public(),
            {
                "profiles": {
                    "10": {
                        "favourite_genres": ["Science Fiction"],
                        "favourite_directors": ["Denis Villeneuve"],
                    },
                    "20": {
                        "favourite_genres": ["Drama"],
                        "favourite_directors": ["Christopher Nolan"],
                    },
                },
                "shared_genres": ["Science Fiction"],
                "shared_directors": [],
            },
            [],
            ["10", "20"],
        )

        self.assertIn(
            "Individual taste data:",
            prompt,
        )

        self.assertIn(
            "A:",
            prompt,
        )

        self.assertIn(
            "B:",
            prompt,
        )

        self.assertIn(
            "Denis Villeneuve",
            prompt,
        )

        self.assertIn(
            "Christopher Nolan",
            prompt,
        )

    def test_prompt_truncates_description(self):
        candidate = self._candidate()

        long_description = " ".join(
            ["A very long movie description"] * 100
        )

        candidate.movie.wikidata_description = long_description

        prompt = _build_prompt(
            self._public(),
            {},
            [candidate],
            ["10", "20"],
        )

        self.assertNotIn(
            long_description,
            prompt,
        )

    def test_prompt_handles_no_candidates(self):
        prompt = _build_prompt(
            self._public(),
            {},
            [],
            ["10", "20"],
        )

        self.assertIn(
            "(none)",
            prompt,
        )

    def test_prompt_handles_missing_internal_values(self):
        prompt = _build_prompt(
            self._public(),
            {},
            [],
            ["10", "20"],
        )

        self.assertIn(
            "Shared favourite genres: none",
            prompt,
        )

        self.assertIn(
            "Shared favourite directors: none",
            prompt,
        )


class ParseTests(TestCase):
    def test_parse_valid_response(self):
        text = """
        {
            "narrative": "You both enjoy science fiction.",
            "individual": {
                "A": "This person prefers science fiction.",
                "B": "This person also enjoys science fiction."
            },
            "recommendations": [
                "It matches both profiles."
            ]
        }
        """

        result = _parse(
            text,
            1,
            ["10", "20"],
        )

        self.assertIsNotNone(result)

        self.assertEqual(
            result.summary,
            "You both enjoy science fiction.",
        )

        self.assertEqual(
            result.reasons,
            {
                1: "It matches both profiles.",
            },
        )

        self.assertEqual(
            result.individual,
            {
                "10": "This person prefers science fiction.",
                "20": "This person also enjoys science fiction.",
            },
        )

    def test_parse_strips_narrative_and_reason(self):
        result = _parse(
            '{"narrative": "  Summary  ", '
            '"individual": {'
            '"A": "  User A taste  ", '
            '"B": "  User B taste  "'
            '}, '
            '"recommendations": ["  Reason  "]}',
            1,
            ["10", "20"],
        )

        self.assertEqual(
            result.summary,
            "Summary",
        )

        self.assertEqual(
            result.reasons,
            {
                1: "Reason",
            },
        )

        self.assertEqual(
            result.individual,
            {
                "10": "User A taste",
                "20": "User B taste",
            },
        )

    def test_parse_ignores_out_of_range_indices(self):
        result = _parse(
            '{"narrative": "Summary", '
            '"individual": {'
            '"A": "User A taste", '
            '"B": "User B taste"'
            '}, '
            '"recommendations": ['
            '{"index": 0, "reason": "zero"},'
            '{"index": 1, "reason": "valid"},'
            '{"index": 3, "reason": "three"}'
            ']}',
            2,
            ["10", "20"],
        )

        self.assertEqual(
            result.reasons,
            {
                1: "valid",
            },
        )

    def test_parse_allows_missing_recommendations(self):
        result = _parse(
            '{"narrative": "Summary", '
            '"individual": {'
            '"A": "User A taste", '
            '"B": "User B taste"'
            '}}',
            2,
            ["10", "20"],
        )

        self.assertIsNotNone(result)

        self.assertEqual(
            result.summary,
            "Summary",
        )

        self.assertEqual(
            result.reasons,
            {},
        )

    def test_parse_invalid_json_returns_none(self):
        self.assertIsNone(
            _parse(
                "not json",
                2,
                ["10", "20"],
            )
        )

    def test_parse_missing_narrative_returns_none(self):
        self.assertIsNone(
            _parse(
                '{"individual": {'
                '"A": "User A taste", '
                '"B": "User B taste"'
                '}, "recommendations": []}',
                2,
                ["10", "20"],
            )
        )

    def test_parse_empty_narrative_returns_none(self):
        self.assertIsNone(
            _parse(
                '{"narrative": "   ", '
                '"individual": {'
                '"A": "User A taste", '
                '"B": "User B taste"'
                '}}',
                2,
                ["10", "20"],
            )
        )

    def test_parse_missing_individual_returns_none(self):
        self.assertIsNone(
            _parse(
                '{"narrative": "Summary", '
                '"recommendations": []}',
                2,
                ["10", "20"],
            )
        )

    def test_parse_invalid_recommendation_returns_none(self):
        self.assertIsNone(
            _parse(
                '{"narrative": "Summary", '
                '"individual": {'
                '"A": "User A taste", '
                '"B": "User B taste"'
                '}, '
                '"recommendations": [{"index": 1}]}',
                1,
                ["10", "20"],
            )
        )

    def test_parse_converts_values_to_strings(self):
        result = _parse(
            '{"narrative": 123, '
            '"individual": {'
            '"A": 456, '
            '"B": 789'
            '}, '
            '"recommendations": [999]}',
            1,
            ["10", "20"],
        )

        self.assertEqual(
            result.summary,
            "123",
        )

        self.assertEqual(
            result.reasons,
            {
                1: "999",
            },
        )

        self.assertEqual(
            result.individual,
            {
                "10": "456",
                "20": "789",
            },
        )


class ComparisonNarrativeClientTests(TestCase):
    @override_settings(GEMINI_API_KEY="settings-key")
    @mock.patch(
        "apps.comparisons.services.narrative.genai.Client"
    )
    def test_uses_settings_api_key_when_not_provided(
        self,
        mock_client,
    ):
        client = ComparisonNarrativeClient()

        mock_client.assert_called_once_with(
            api_key="settings-key",
        )

        self.assertEqual(
            client.model,
            DEFAULT_MODEL,
        )

    @mock.patch(
        "apps.comparisons.services.narrative.genai.Client"
    )
    def test_uses_explicit_api_key(
        self,
        mock_client,
    ):
        ComparisonNarrativeClient(
            api_key="explicit-key",
        )

        mock_client.assert_called_once_with(
            api_key="explicit-key",
        )

    @mock.patch(
        "apps.comparisons.services.narrative.genai.Client"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.consume"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.cost_units"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.estimate_tokens"
    )
    def test_generate_returns_none_when_quota_is_exceeded(
        self,
        mock_estimate_tokens,
        mock_cost_units,
        mock_consume,
        mock_client,
    ):
        mock_estimate_tokens.return_value = 10
        mock_cost_units.return_value = 5

        mock_consume.side_effect = QuotaExceeded(
            QUOTA_CLIENT_NAME,
            "day",
            10,
        )

        client = ComparisonNarrativeClient(
            api_key="test-key",
        )

        result = client.generate(
            public={
                "compatibility_score": 85,
                "taste_similarity": 0.8,
                "library_sizes": {
                    "1": 10,
                    "2": 12,
                },
                "common_count": 5,
                "overlap_ratio": 0.5,
                "jaccard": 0.3,
                "mean_rating_gap": 0.5,
                "rating_correlation": 0.8,
                "agreements": [],
                "divergences": [],
            },
            internal={
                "shared_genres": [],
                "shared_directors": [],
            },
            candidates=[],
            user_ids=["1", "2"],
        )

        self.assertIsNone(
            result,
        )

        mock_consume.assert_called_once_with(
            QUOTA_CLIENT_NAME,
            5,
        )

        mock_client.return_value.models.generate_content.assert_not_called()

    @mock.patch(
        "apps.comparisons.services.narrative.genai.Client"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.adjust"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.cost_units"
    )
    def test_reconcile_cost_adjusts_actual_difference(
        self,
        mock_cost_units,
        mock_adjust,
        mock_client,
    ):
        mock_cost_units.return_value = 12

        usage = mock.Mock()
        usage.prompt_token_count = 50
        usage.candidates_token_count = 20
        usage.thoughts_token_count = 5

        response = mock.Mock()
        response.usage_metadata = usage

        ComparisonNarrativeClient._reconcile_cost(
            response,
            reserved=10,
        )

        mock_cost_units.assert_called_once_with(
            QUOTA_CLIENT_NAME,
            input_tokens=50,
            output_tokens=25,
        )

        mock_adjust.assert_called_once_with(
            QUOTA_CLIENT_NAME,
            2,
        )

    def test_reconcile_cost_does_nothing_without_usage(self):
        response = mock.Mock()
        response.usage_metadata = None

        with mock.patch(
            "apps.comparisons.services.narrative.api_quota.adjust"
        ) as mock_adjust:
            ComparisonNarrativeClient._reconcile_cost(
                response,
                reserved=10,
            )

        mock_adjust.assert_not_called()

    def test_reconcile_cost_does_nothing_without_prompt_count(self):
        usage = mock.Mock()
        usage.prompt_token_count = None

        response = mock.Mock()
        response.usage_metadata = usage

        with mock.patch(
            "apps.comparisons.services.narrative.api_quota.adjust"
        ) as mock_adjust:
            ComparisonNarrativeClient._reconcile_cost(
                response,
                reserved=10,
            )

        mock_adjust.assert_not_called()

    @mock.patch(
        "apps.comparisons.services.narrative.genai.Client"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.adjust"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.cost_units"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.consume"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.estimate_tokens"
    )
    def test_generate_calls_gemini_and_parses_response(
        self,
        mock_estimate_tokens,
        mock_consume,
        mock_cost_units,
        mock_adjust,
        mock_client,
    ):
        mock_estimate_tokens.return_value = 50

        mock_cost_units.side_effect = [
            10,
            12,
        ]

        usage = mock.Mock()
        usage.prompt_token_count = 50
        usage.candidates_token_count = 20
        usage.thoughts_token_count = 0

        response = mock.Mock()
        response.text = (
            '{"narrative": "You have similar tastes.", '
            '"individual": {'
            '"A": "This person enjoys science fiction.", '
            '"B": "This person also enjoys science fiction."'
            '}, '
            '"recommendations": ['
            '"Good fit."'
            ']}'
        )
        response.usage_metadata = usage

        mock_client.return_value.models.generate_content.return_value = (
            response
        )

        candidate = mock.Mock()
        candidate.movie = mock.Mock()
        candidate.movie.title = "Dune"
        candidate.movie.release_year = 2021
        candidate.movie.wikidata_description = "A science-fiction epic."
        candidate.movie.genres.all.return_value = []
        candidate.per_user = [0.91, 0.84]

        client = ComparisonNarrativeClient(
            api_key="test-key",
        )

        result = client.generate(
            public={
                "compatibility_score": 85,
                "taste_similarity": 0.8,
                "library_sizes": {
                    "1": 10,
                    "2": 12,
                },
                "common_count": 5,
                "overlap_ratio": 0.5,
                "jaccard": 0.3,
                "mean_rating_gap": 0.5,
                "rating_correlation": 0.8,
                "agreements": [],
                "divergences": [],
            },
            internal={
                "shared_genres": [],
                "shared_directors": [],
            },
            candidates=[candidate],
            user_ids=["1", "2"],
        )

        self.assertIsNotNone(
            result,
        )

        self.assertEqual(
            result.summary,
            "You have similar tastes.",
        )

        self.assertEqual(
            result.reasons,
            {
                1: "Good fit.",
            },
        )

        self.assertEqual(
            result.individual,
            {
                "1": "This person enjoys science fiction.",
                "2": "This person also enjoys science fiction.",
            },
        )

        mock_consume.assert_called_once_with(
            QUOTA_CLIENT_NAME,
            10,
        )

        mock_adjust.assert_called_once_with(
            QUOTA_CLIENT_NAME,
            2,
        )

        mock_client.return_value.models.generate_content.assert_called_once()

    @mock.patch(
        "apps.comparisons.services.narrative.genai.Client"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.adjust"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.cost_units"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.consume"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.estimate_tokens"
    )
    def test_generate_returns_none_for_unparseable_response(
        self,
        mock_estimate_tokens,
        mock_consume,
        mock_cost_units,
        mock_adjust,
        mock_client,
    ):
        mock_estimate_tokens.return_value = 10
        mock_cost_units.side_effect = [
            5,
            5,
        ]

        response = mock.Mock()
        response.text = "not json"
        response.usage_metadata = None

        mock_client.return_value.models.generate_content.return_value = (
            response
        )

        client = ComparisonNarrativeClient(
            api_key="test-key",
        )

        result = client.generate(
            public={
                "compatibility_score": 85,
                "taste_similarity": 0.8,
                "library_sizes": {
                    "1": 10,
                    "2": 12,
                },
                "common_count": 5,
                "overlap_ratio": 0.5,
                "jaccard": 0.3,
                "mean_rating_gap": 0.5,
                "rating_correlation": 0.8,
                "agreements": [],
                "divergences": [],
            },
            internal={
                "shared_genres": [],
                "shared_directors": [],
            },
            candidates=[],
            user_ids=["1", "2"],
        )

        self.assertIsNone(
            result,
        )

    @mock.patch(
        "apps.comparisons.services.narrative.genai.Client"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.consume"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.cost_units"
    )
    @mock.patch(
        "apps.comparisons.services.narrative.api_quota.estimate_tokens"
    )
    def test_generate_returns_none_on_gemini_exception(
        self,
        mock_estimate_tokens,
        mock_cost_units,
        mock_consume,
        mock_client,
    ):
        mock_estimate_tokens.return_value = 10
        mock_cost_units.return_value = 5

        mock_client.return_value.models.generate_content.side_effect = (
            RuntimeError("Gemini failed")
        )

        client = ComparisonNarrativeClient(
            api_key="test-key",
        )

        result = client.generate(
            public={
                "compatibility_score": 85,
                "taste_similarity": 0.8,
                "library_sizes": {
                    "1": 10,
                    "2": 12,
                },
                "common_count": 5,
                "overlap_ratio": 0.5,
                "jaccard": 0.3,
                "mean_rating_gap": 0.5,
                "rating_correlation": 0.8,
                "agreements": [],
                "divergences": [],
            },
            internal={
                "shared_genres": [],
                "shared_directors": [],
            },
            candidates=[],
            user_ids=["1", "2"],
        )

        self.assertIsNone(
            result,
        )
