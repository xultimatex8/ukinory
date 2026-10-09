from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from apps.common.api_quota import QuotaExceeded
from apps.comparisons.services.narrative import (
    BASE_OUTPUT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL,
    MAX_DESCRIPTION_CHARS,
    PROMPT_ENTRIES,
    ComparisonNarrativeClient,
    _build_prompt,
    _compact_public,
    _max_output_tokens,
    _shorten,
    _story_angles,
)


class HelperTests(TestCase):
    def test_max_output_tokens(self):
        self.assertEqual(
            _max_output_tokens(0),
            BASE_OUTPUT_TOKENS,
        )
        self.assertEqual(
            _max_output_tokens(10),
            DEFAULT_MAX_OUTPUT_TOKENS,
        )

    def test_shorten_keeps_short_text(self):
        self.assertEqual(
            _shorten("Short description", 100),
            "Short description",
        )

    def test_shorten_truncates_at_word_boundary(self):
        text = "This is a long movie description with many different words."

        result = _shorten(text, 30)

        self.assertLessEqual(len(result), 30)
        self.assertFalse(result.endswith(" "))
        self.assertNotEqual(result, text)

    def test_shorten_handles_empty_text(self):
        self.assertEqual(_shorten("", 100), "")
        self.assertEqual(_shorten(None, 100), "")


class CompactPublicTests(TestCase):
    def test_compact_public_uses_labels_and_limits_entries(self):
        public = {
            "compatibility_score": 85,
            "taste_similarity": 0.8,
            "common_count": 5,
            "mean_rating_gap": 0.5,
            "rating_correlation": 0.8,
            "library_sizes": {
                "1": 10,
                "2": 12,
            },
            "agreements": [
                {
                    "title": "Dune",
                    "release_year": 2021,
                    "ratings": {
                        "1": 5,
                        "2": 4,
                    },
                },
                {
                    "title": "Alien",
                    "release_year": 1979,
                    "ratings": {
                        "1": 5,
                        "2": 5,
                    },
                },
                {
                    "title": "Jaws",
                    "release_year": 1975,
                    "ratings": {
                        "1": 4,
                        "2": 5,
                    },
                },
                {
                    "title": "Extra",
                    "release_year": 2000,
                    "ratings": {
                        "1": 3,
                        "2": 3,
                    },
                },
            ],
            "divergences": [],
        }

        result = _compact_public(
            public,
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertEqual(result["compatibility_score"], 85)
        self.assertEqual(result["taste_similarity"], 0.8)
        self.assertEqual(result["common_films"], 5)
        self.assertEqual(result["mean_rating_gap"], 0.5)
        self.assertEqual(result["rating_correlation"], 0.8)
        self.assertEqual(
            result["library_sizes"],
            {
                "A": 10,
                "B": 12,
            },
        )
        self.assertEqual(len(result["agreements"]), PROMPT_ENTRIES)
        self.assertEqual(result["agreements"][0]["title"], "Dune")
        self.assertEqual(
            result["agreements"][0]["ratings"],
            {
                "A": 5,
                "B": 4,
            },
        )


class StoryAnglesTests(TestCase):
    def test_similar_taste_but_different_ratings(self):
        public = {
            "taste_similarity": 0.8,
            "rating_correlation": 0.1,
            "common_count": 20,
            "library_sizes": {
                "1": 20,
                "2": 20,
            },
            "divergences": [],
            "agreements": [],
        }

        result = _story_angles(
            public,
            {"profiles": {}},
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertIn(
            "Similar taste on paper, but they score the same films very differently.",
            result,
        )

    def test_low_similarity(self):
        public = {
            "taste_similarity": 0.2,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {
                "1": 20,
                "2": 20,
            },
            "divergences": [],
            "agreements": [],
        }

        result = _story_angles(
            public,
            {"profiles": {}},
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertIn(
            "Their tastes pull in clearly different directions.",
            result,
        )

    def test_divergence_is_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {
                "1": 20,
                "2": 20,
            },
            "divergences": [
                {
                    "title": "Blade Runner",
                    "ratings": {
                        "1": 5,
                        "2": 2,
                    },
                }
            ],
            "agreements": [],
        }

        result = _story_angles(
            public,
            {"profiles": {}},
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertIn(
            "Sharpest clash: Blade Runner (A=5 vs B=2).",
            result,
        )

    def test_rating_style_gap_is_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {
                "1": 20,
                "2": 20,
            },
            "divergences": [],
            "agreements": [],
        }

        internal = {
            "profiles": {
                "1": {
                    "mean_rating": 4.5,
                },
                "2": {
                    "mean_rating": 3.2,
                },
            }
        }

        result = _story_angles(
            public,
            internal,
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertIn(
            "Rating style gap: A is far more generous than B.",
            result,
        )

    def test_agreement_is_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {
                "1": 20,
                "2": 20,
            },
            "divergences": [],
            "agreements": [
                {
                    "title": "Alien",
                    "ratings": {
                        "1": 5,
                        "2": 5,
                    },
                }
            ],
        }

        result = _story_angles(
            public,
            {"profiles": {}},
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertIn(
            "Common ground: both rated Alien very high (A=5 vs B=5).",
            result,
        )

    def test_shared_director_takes_precedence_over_genre(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {
                "1": 20,
                "2": 20,
            },
            "divergences": [],
            "agreements": [],
        }

        internal = {
            "profiles": {},
            "shared_directors": ["Christopher Nolan"],
            "shared_genres": ["Sci-Fi"],
        }

        result = _story_angles(
            public,
            internal,
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertIn(
            "Shared favourite director: Christopher Nolan.",
            result,
        )
        self.assertNotIn(
            "Shared favourite genre: Sci-Fi.",
            result,
        )

    def test_shared_genre_is_used_without_shared_director(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {
                "1": 20,
                "2": 20,
            },
            "divergences": [],
            "agreements": [],
        }

        internal = {
            "profiles": {},
            "shared_directors": [],
            "shared_genres": ["Sci-Fi"],
        }

        result = _story_angles(
            public,
            internal,
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertIn(
            "Shared favourite genre: Sci-Fi.",
            result,
        )

    def test_few_common_films_is_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 5,
            "library_sizes": {
                "1": 20,
                "2": 20,
            },
            "divergences": [],
            "agreements": [],
        }

        result = _story_angles(
            public,
            {"profiles": {}},
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertIn(
            "They have rated very few of the same films.",
            result,
        )

    def test_uneven_library_sizes_are_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {
                "1": 10,
                "2": 40,
            },
            "divergences": [],
            "agreements": [],
        }

        result = _story_angles(
            public,
            {"profiles": {}},
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertIn(
            "One of them has rated far more films than the other.",
            result,
        )

    def test_returns_fallback_when_no_angle_exists(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {
                "1": 20,
                "2": 20,
            },
            "divergences": [],
            "agreements": [],
        }

        result = _story_angles(
            public,
            {
                "profiles": {},
                "shared_directors": [],
                "shared_genres": [],
            },
            {
                "1": "A",
                "2": "B",
            },
        )

        self.assertEqual(
            result,
            [
                "No standout pattern: focus on their favourite films and genres."
            ],
        )


class BuildPromptTests(TestCase):
    def _public(self):
        return {
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
        }

    def _internal(self):
        return {
            "profiles": {
                "1": {
                    "mean_rating": 4.2,
                    "favourite_genres": ["Sci-Fi"],
                },
                "2": {
                    "mean_rating": 3.8,
                    "favourite_genres": ["Drama"],
                },
            },
            "shared_genres": ["Sci-Fi"],
            "shared_directors": ["Denis Villeneuve"],
        }

    def _candidate(
        self,
        title="Dune",
        description="A science-fiction epic.",
        genres=None,
        directors=None,
    ):
        movie = mock.Mock(
            title=title,
            release_year=2021,
            wikidata_description=description,
        )

        movie.directors = directors or []

        genre_names = genres or ["Sci-Fi", "Adventure"]
        movie.genres.all.return_value = [
            SimpleNamespace(name=name)
            for name in genre_names
        ]

        return mock.Mock(
            movie=movie,
            per_user=[0.91, 0.84],
        )

    def test_prompt_contains_candidate_information(self):
        candidate = self._candidate(
            title="Dune",
            description="A science-fiction epic.",
            genres=["Sci-Fi", "Adventure"],
            directors=["Denis Villeneuve"],
        )

        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [candidate],
            ["1", "2"],
        )

        self.assertIn("Dune (2021)", prompt)
        self.assertIn("Sci-Fi, Adventure", prompt)
        self.assertIn("dir. Denis Villeneuve", prompt)
        self.assertIn("fit A=0.91 B=0.84", prompt)
        self.assertIn("A science-fiction epic.", prompt)

    def test_prompt_truncates_description(self):
        description = (
            "This is a very long description of a science fiction movie "
            "that should definitely be truncated before being included "
            "inside the prompt."
        )

        candidate = self._candidate(
            description=description,
        )

        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [candidate],
            ["1", "2"],
        )

        self.assertIn(
            description[:MAX_DESCRIPTION_CHARS].rsplit(" ", 1)[0],
            prompt,
        )
        self.assertNotIn(description, prompt)

    def test_prompt_contains_story_angles(self):
        candidate = self._candidate()

        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [candidate],
            ["1", "2"],
        )

        self.assertIn("Story angles", prompt)
        self.assertIn(
            "Shared favourite director: Denis Villeneuve.",
            prompt,
        )

    def test_prompt_contains_profiles(self):
        candidate = self._candidate()

        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [candidate],
            ["1", "2"],
        )

        self.assertIn("Individual taste data:", prompt)
        self.assertIn('"mean_rating":4.2', prompt)
        self.assertIn('"mean_rating":3.8', prompt)

    def test_prompt_contains_schema_and_rules(self):
        candidate = self._candidate()

        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [candidate],
            ["1", "2"],
        )

        self.assertIn(
            '{"narrative": str, "individual": {"A": str, "B": str}',
            prompt,
        )
        self.assertIn(
            "recommendations: exactly 1 strings",
            prompt,
        )
        self.assertIn(
            "Do not mention or repeat the recommended film's title.",
            prompt,
        )

    def test_prompt_without_candidates_uses_none(self):
        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [],
            ["1", "2"],
        )

        self.assertIn(
            "Candidates (neither has watched them):\n(none)",
            prompt,
        )
        self.assertIn(
            "recommendations: an empty list.",
            prompt,
        )


class ComparisonNarrativeClientTests(TestCase):
    def _public(self):
        return {
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
        }

    def _generate(self, client, candidates=()):
        return client.generate(
            public=self._public(),
            internal={
                "shared_genres": [],
                "shared_directors": [],
            },
            candidates=candidates,
            user_ids=["1", "2"],
        )

    def _candidate(self):
        movie = mock.Mock(
            title="Dune",
            release_year=2021,
            wikidata_description="A science-fiction epic.",
        )

        movie.directors = []

        movie.genres.all.return_value = [
            SimpleNamespace(name="Sci-Fi"),
        ]

        return mock.Mock(
            movie=movie,
            per_user=[0.91, 0.84],
        )

    @override_settings(GEMINI_API_KEY="settings-key")
    @mock.patch("apps.comparisons.services.narrative.genai.Client")
    def test_uses_settings_api_key(self, mock_client):
        client = ComparisonNarrativeClient()

        mock_client.assert_called_once_with(
            api_key="settings-key",
        )
        self.assertEqual(
            client.model,
            DEFAULT_MODEL,
        )

    @mock.patch("apps.comparisons.services.narrative.genai.Client")
    def test_uses_explicit_api_key(self, mock_client):
        ComparisonNarrativeClient(
            api_key="explicit-key",
        )

        mock_client.assert_called_once_with(
            api_key="explicit-key",
        )

    @mock.patch("apps.comparisons.services.narrative.genai.Client")
    @mock.patch("apps.comparisons.services.narrative.api_quota.consume")
    @mock.patch("apps.comparisons.services.narrative.api_quota.cost_units")
    @mock.patch("apps.comparisons.services.narrative.api_quota.estimate_tokens")
    def test_generate_returns_none_when_quota_is_exceeded(
        self,
        estimate,
        cost,
        consume,
        client_mock,
    ):
        estimate.return_value = 10
        cost.return_value = 5

        consume.side_effect = QuotaExceeded(
            "gemini_narrative",
            "day",
            10,
        )

        client = ComparisonNarrativeClient(
            api_key="test-key",
        )

        self.assertIsNone(
            self._generate(client),
        )

        consume.assert_called_once_with(
            "gemini_narrative",
            5,
        )

        client_mock.return_value.models.generate_content.assert_not_called()

    @mock.patch("apps.comparisons.services.narrative.api_quota.adjust")
    @mock.patch("apps.comparisons.services.narrative.api_quota.cost_units")
    def test_reconcile_cost_adjusts_actual_difference(
        self,
        cost,
        adjust,
    ):
        cost.return_value = 12

        response = mock.Mock(
            usage_metadata=mock.Mock(
                prompt_token_count=50,
                candidates_token_count=20,
                thoughts_token_count=5,
            ),
        )

        ComparisonNarrativeClient._reconcile_cost(
            response,
            reserved=10,
        )

        cost.assert_called_once_with(
            "gemini_narrative",
            input_tokens=50,
            output_tokens=25,
        )

        adjust.assert_called_once_with(
            "gemini_narrative",
            2,
        )

    def test_reconcile_cost_does_nothing_without_usage(self):
        response = mock.Mock(
            usage_metadata=None,
        )

        with mock.patch(
            "apps.comparisons.services.narrative.api_quota.adjust",
        ) as adjust:
            ComparisonNarrativeClient._reconcile_cost(
                response,
                10,
            )

        adjust.assert_not_called()

    def test_reconcile_cost_does_nothing_without_prompt_count(self):
        response = mock.Mock(
            usage_metadata=mock.Mock(
                prompt_token_count=None,
            ),
        )

        with mock.patch(
            "apps.comparisons.services.narrative.api_quota.adjust",
        ) as adjust:
            ComparisonNarrativeClient._reconcile_cost(
                response,
                10,
            )

        adjust.assert_not_called()

    @mock.patch("apps.comparisons.services.narrative.genai.Client")
    @mock.patch("apps.comparisons.services.narrative.api_quota.adjust")
    @mock.patch("apps.comparisons.services.narrative.api_quota.cost_units")
    @mock.patch("apps.comparisons.services.narrative.api_quota.consume")
    @mock.patch("apps.comparisons.services.narrative.api_quota.estimate_tokens")
    def test_generate_calls_gemini_and_parses_response(
        self,
        estimate,
        consume,
        cost,
        adjust,
        client_mock,
    ):
        estimate.return_value = 50
        cost.side_effect = [10, 12]

        response = mock.Mock(
            text=(
                '{"narrative":"You have similar tastes.",'
                '"individual":{'
                '"A":"This person enjoys science fiction.",'
                '"B":"This person also enjoys science fiction."},'
                '"recommendations":["Good fit."]}'
            ),
            usage_metadata=mock.Mock(
                prompt_token_count=50,
                candidates_token_count=20,
                thoughts_token_count=0,
            ),
        )

        client_mock.return_value.models.generate_content.return_value = (
            response
        )

        client = ComparisonNarrativeClient(
            api_key="test-key",
        )

        result = self._generate(
            client,
            [self._candidate()],
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

        consume.assert_called_once_with(
            "gemini_narrative",
            10,
        )

        adjust.assert_called_once_with(
            "gemini_narrative",
            2,
        )

        client_mock.return_value.models.generate_content.assert_called_once()

    @mock.patch("apps.comparisons.services.narrative.genai.Client")
    @mock.patch("apps.comparisons.services.narrative.api_quota.adjust")
    @mock.patch("apps.comparisons.services.narrative.api_quota.cost_units")
    @mock.patch("apps.comparisons.services.narrative.api_quota.consume")
    @mock.patch("apps.comparisons.services.narrative.api_quota.estimate_tokens")
    def test_generate_returns_none_for_unparseable_response(
        self,
        estimate,
        consume,
        cost,
        adjust,
        client_mock,
    ):
        estimate.return_value = 10
        cost.side_effect = [5, 5]

        client_mock.return_value.models.generate_content.return_value = (
            mock.Mock(
                text="not json",
                usage_metadata=None,
            )
        )

        self.assertIsNone(
            self._generate(
                ComparisonNarrativeClient(
                    api_key="test-key",
                ),
            ),
        )

    @mock.patch("apps.comparisons.services.narrative.genai.Client")
    @mock.patch("apps.comparisons.services.narrative.api_quota.consume")
    @mock.patch("apps.comparisons.services.narrative.api_quota.cost_units")
    @mock.patch("apps.comparisons.services.narrative.api_quota.estimate_tokens")
    def test_generate_returns_none_on_gemini_exception(
        self,
        estimate,
        cost,
        consume,
        client_mock,
    ):
        estimate.return_value = 10
        cost.return_value = 5

        client_mock.return_value.models.generate_content.side_effect = (
            RuntimeError("Gemini failed")
        )

        self.assertIsNone(
            self._generate(
                ComparisonNarrativeClient(
                    api_key="test-key",
                ),
            ),
        )
