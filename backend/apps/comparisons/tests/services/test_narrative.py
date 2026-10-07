from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from apps.common.exceptions import QuotaExceeded
from apps.comparisons.services.narrative import (
    DEFAULT_MODEL,
    MAX_DESCRIPTION_CHARS,
    ComparisonNarrativeClient,
    _anonymise,
    _build_prompt,
    _labels,
    _parse,
)


class LabelsTests(TestCase):
    def test_labels_two_users(self):
        self.assertEqual(
            _labels(["10", "20"]),
            {
                "10": "User A",
                "20": "User B",
            },
        )

    def test_labels_multiple_users(self):
        self.assertEqual(
            _labels(["1", "2", "3"]),
            {
                "1": "User A",
                "2": "User B",
                "3": "User C",
            },
        )


class AnonymiseTests(TestCase):
    def test_anonymises_library_sizes(self):
        public = {
            "library_sizes": {
                "10": 100,
                "20": 80,
            },
            "agreements": [],
            "divergences": [],
        }

        result = _anonymise(
            public,
            _labels(["10", "20"]),
        )

        self.assertEqual(
            result["library_sizes"],
            {
                "User A": 100,
                "User B": 80,
            },
        )

    def test_anonymises_ratings(self):
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

        result = _anonymise(
            public,
            _labels(["10", "20"]),
        )

        self.assertEqual(
            result["agreements"][0]["ratings"],
            {
                "User A": 5.0,
                "User B": 4.5,
            },
        )

        self.assertEqual(
            result["divergences"][0]["ratings"],
            {
                "User A": 2.0,
                "User B": 5.0,
            },
        )

    def test_does_not_mutate_public(self):
        public = {
            "library_sizes": {
                "10": 100,
                "20": 80,
            },
            "agreements": [],
            "divergences": [],
        }

        original = {
            "library_sizes": {
                "10": 100,
                "20": 80,
            },
            "agreements": [],
            "divergences": [],
        }

        _anonymise(
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
            "Compatibility metrics:",
            prompt,
        )

        self.assertIn(
            "compatibility_score",
            prompt,
        )

        self.assertIn(
            "User A",
            prompt,
        )

        self.assertIn(
            "User B",
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
            "taste fit: User A=0.91, User B=0.84",
            prompt,
        )

        self.assertIn(
            "A science-fiction epic.",
            prompt,
        )

    def test_prompt_truncates_description(self):
        candidate = self._candidate()

        candidate.movie.wikidata_description = "x" * (
            MAX_DESCRIPTION_CHARS + 100
        )

        prompt = _build_prompt(
            self._public(),
            {},
            [candidate],
            ["10", "20"],
        )

        self.assertNotIn(
            "x" * (MAX_DESCRIPTION_CHARS + 1),
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
            "recommendations": [
                {
                    "index": 1,
                    "reason": "It matches both profiles."
                }
            ]
        }
        """

        result = _parse(
            text,
            2,
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

    def test_parse_strips_narrative_and_reason(self):
        result = _parse(
            '{"narrative": "  Summary  ", '
            '"recommendations": [{"index": 1, "reason": "  Reason  "}]}',
            1,
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

    def test_parse_ignores_out_of_range_indices(self):
        result = _parse(
            '{"narrative": "Summary", '
            '"recommendations": ['
            '{"index": 0, "reason": "zero"},'
            '{"index": 1, "reason": "valid"},'
            '{"index": 3, "reason": "three"}'
            ']}',
            2,
        )

        self.assertEqual(
            result.reasons,
            {
                1: "valid",
            },
        )

    def test_parse_allows_missing_recommendations(self):
        result = _parse(
            '{"narrative": "Summary"}',
            2,
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
            )
        )

    def test_parse_missing_narrative_returns_none(self):
        self.assertIsNone(
            _parse(
                '{"recommendations": []}',
                2,
            )
        )

    def test_parse_empty_narrative_returns_none(self):
        self.assertIsNone(
            _parse(
                '{"narrative": "   "}',
                2,
            )
        )

    def test_parse_invalid_recommendation_returns_none(self):
        self.assertIsNone(
            _parse(
                '{"narrative": "Summary", '
                '"recommendations": [{"reason": "Missing index"}]}',
                1,
            )
        )

    def test_parse_converts_values_to_strings(self):
        result = _parse(
            '{"narrative": 123, '
            '"recommendations": [{"index": 1, "reason": 456}]}',
            1,
        )

        self.assertEqual(
            result.summary,
            "123",
        )

        self.assertEqual(
            result.reasons,
            {
                1: "456",
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
            "gemini_generate",
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

        mock_consume.assert_called_once()

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
            "gemini_generate",
            input_tokens=50,
            output_tokens=25,
        )

        mock_adjust.assert_called_once_with(
            "gemini_generate",
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
            '"recommendations": ['
            '{"index": 1, "reason": "Good fit."}'
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

        mock_consume.assert_called_once_with(
            "gemini_generate",
            10,
        )

        mock_adjust.assert_called_once_with(
            "gemini_generate",
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
