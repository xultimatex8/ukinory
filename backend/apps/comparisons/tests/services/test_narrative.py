from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

from django.test import override_settings

from apps.common.exceptions import AIUnavailableError
from apps.common.services.gemini import Completion, DEFAULT_MODEL
from apps.comparisons.services.narrative import (
    BASE_OUTPUT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    MAX_ANGLES,
    MAX_DESCRIPTION_CHARS,
    PROMPT_ENTRIES,
    ComparisonNarrativeClient,
    _build_prompt,
    _candidate_line,
    _compact_public,
    _fmt_ratings,
    _json,
    _labels,
    _letters,
    _max_output_tokens,
    _parse,
    _profiles_block,
    _shorten,
    _story_angles,
)


class TestHelper:
    def test_max_output_tokens(self):
        assert _max_output_tokens(0) == BASE_OUTPUT_TOKENS
        assert _max_output_tokens(10) == DEFAULT_MAX_OUTPUT_TOKENS

    def test_shorten_keeps_short_text(self):
        assert _shorten("Short description", 100) == "Short description"

    def test_shorten_truncates_at_word_boundary(self):
        text = "This is a long movie description with many different words."

        result = _shorten(text, 30)

        assert len(result) <= 30
        assert not result.endswith(" ")
        assert result != text

    def test_shorten_handles_empty_text(self):
        assert _shorten("", 100) == ""
        assert _shorten(None, 100) == ""


class TestCompactPublic:
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
                    "ratings": {"1": 5, "2": 4},
                },
                {
                    "title": "Alien",
                    "release_year": 1979,
                    "ratings": {"1": 5, "2": 5},
                },
                {
                    "title": "Jaws",
                    "release_year": 1975,
                    "ratings": {"1": 4, "2": 5},
                },
                {
                    "title": "Extra",
                    "release_year": 2000,
                    "ratings": {"1": 3, "2": 3},
                },
            ],
            "divergences": [],
        }

        result = _compact_public(public, {"1": "A", "2": "B"})

        assert result["compatibility_score"] == 85
        assert result["taste_similarity"] == 0.8
        assert result["common_films"] == 5
        assert result["mean_rating_gap"] == 0.5
        assert result["rating_correlation"] == 0.8
        assert result["library_sizes"] == {"A": 10, "B": 12}
        assert len(result["agreements"]) == PROMPT_ENTRIES
        assert result["agreements"][0]["title"] == "Dune"
        assert result["agreements"][0]["ratings"] == {"A": 5, "B": 4}


class TestStoryAngles:
    def test_similar_taste_but_different_ratings(self):
        public = {
            "taste_similarity": 0.8,
            "rating_correlation": 0.1,
            "common_count": 20,
            "library_sizes": {"1": 20, "2": 20},
            "divergences": [],
            "agreements": [],
        }

        result = _story_angles(public, {"profiles": {}}, {"1": "A", "2": "B"})

        assert "Similar taste on paper, but they score the same films very differently." in result

    def test_low_similarity(self):
        public = {
            "taste_similarity": 0.2,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {"1": 20, "2": 20},
            "divergences": [],
            "agreements": [],
        }

        result = _story_angles(public, {"profiles": {}}, {"1": "A", "2": "B"})

        assert "Their tastes pull in clearly different directions." in result

    def test_divergence_is_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {"1": 20, "2": 20},
            "divergences": [
                {
                    "title": "Blade Runner",
                    "ratings": {"1": 5, "2": 2},
                }
            ],
            "agreements": [],
        }

        result = _story_angles(public, {"profiles": {}}, {"1": "A", "2": "B"})

        assert "Sharpest clash: Blade Runner (A=5 vs B=2)." in result

    def test_rating_style_gap_is_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {"1": 20, "2": 20},
            "divergences": [],
            "agreements": [],
        }
        internal = {
            "profiles": {
                "1": {"mean_rating": 4.5},
                "2": {"mean_rating": 3.2},
            }
        }

        result = _story_angles(public, internal, {"1": "A", "2": "B"})

        assert "Rating style gap: A is far more generous than B." in result

    def test_agreement_is_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {"1": 20, "2": 20},
            "divergences": [],
            "agreements": [
                {
                    "title": "Alien",
                    "ratings": {"1": 5, "2": 5},
                }
            ],
        }

        result = _story_angles(public, {"profiles": {}}, {"1": "A", "2": "B"})

        assert "Common ground: both rated Alien very high (A=5 vs B=5)." in result

    def test_shared_director_takes_precedence_over_genre(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {"1": 20, "2": 20},
            "divergences": [],
            "agreements": [],
        }
        internal = {
            "profiles": {},
            "shared_directors": ["Christopher Nolan"],
            "shared_genres": ["Sci-Fi"],
        }

        result = _story_angles(public, internal, {"1": "A", "2": "B"})

        assert "Shared favourite director: Christopher Nolan." in result
        assert "Shared favourite genre: Sci-Fi." not in result

    def test_shared_genre_is_used_without_shared_director(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {"1": 20, "2": 20},
            "divergences": [],
            "agreements": [],
        }
        internal = {
            "profiles": {},
            "shared_directors": [],
            "shared_genres": ["Sci-Fi"],
        }

        result = _story_angles(public, internal, {"1": "A", "2": "B"})

        assert "Shared favourite genre: Sci-Fi." in result

    def test_few_common_films_is_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 5,
            "library_sizes": {"1": 20, "2": 20},
            "divergences": [],
            "agreements": [],
        }

        result = _story_angles(public, {"profiles": {}}, {"1": "A", "2": "B"})

        assert "They have rated very few of the same films." in result

    def test_uneven_library_sizes_are_used(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {"1": 10, "2": 40},
            "divergences": [],
            "agreements": [],
        }

        result = _story_angles(public, {"profiles": {}}, {"1": "A", "2": "B"})

        assert "One of them has rated far more films than the other." in result

    def test_returns_fallback_when_no_angle_exists(self):
        public = {
            "taste_similarity": 0.5,
            "rating_correlation": 0.5,
            "common_count": 20,
            "library_sizes": {"1": 20, "2": 20},
            "divergences": [],
            "agreements": [],
        }
        internal = {
            "profiles": {},
            "shared_directors": [],
            "shared_genres": [],
        }

        result = _story_angles(public, internal, {"1": "A", "2": "B"})

        assert result == [
            "No standout pattern: focus on their favourite films and genres."
        ]


class TestBuildPrompt:
    def _public(self):
        return {
            "compatibility_score": 85,
            "taste_similarity": 0.8,
            "library_sizes": {"1": 10, "2": 12},
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
        movie.genres.all.return_value = [
            SimpleNamespace(name=name)
            for name in (genres or ["Sci-Fi", "Adventure"])
        ]

        return mock.Mock(movie=movie, per_user=[0.91, 0.84])

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

        assert "Dune (2021)" in prompt
        assert "Sci-Fi, Adventure" in prompt
        assert "dir. Denis Villeneuve" in prompt
        assert "fit A=0.91 B=0.84" in prompt
        assert "A science-fiction epic." in prompt

    def test_prompt_truncates_description(self):
        description = (
            "This is a very long description of a science fiction movie "
            "that should definitely be truncated before being included "
            "inside the prompt."
        )
        candidate = self._candidate(description=description)

        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [candidate],
            ["1", "2"],
        )

        assert description[:MAX_DESCRIPTION_CHARS].rsplit(" ", 1)[0] in prompt
        assert description not in prompt

    def test_prompt_contains_story_angles(self):
        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [self._candidate()],
            ["1", "2"],
        )

        assert "Story angles" in prompt
        assert "Shared favourite director: Denis Villeneuve." in prompt

    def test_prompt_contains_profiles(self):
        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [self._candidate()],
            ["1", "2"],
        )

        assert "Individual taste data:" in prompt
        assert '"mean_rating":4.2' in prompt
        assert '"mean_rating":3.8' in prompt

    def test_prompt_contains_schema_and_rules(self):
        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [self._candidate()],
            ["1", "2"],
        )

        assert '{"narrative": str, "individual": {"A": str, "B": str}' in prompt
        assert "recommendations: exactly 1 strings" in prompt
        assert "Do not mention or repeat the recommended film's title." in prompt

    def test_prompt_without_candidates_uses_none(self):
        prompt = _build_prompt(
            self._public(),
            self._internal(),
            [],
            ["1", "2"],
        )

        assert "Candidates (neither has watched them):\n(none)" in prompt
        assert "recommendations: an empty list." in prompt


class TestComparisonNarrativeClient:
    def _public(self):
        return {
            "compatibility_score": 85,
            "taste_similarity": 0.8,
            "library_sizes": {"1": 10, "2": 12},
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

        return mock.Mock(movie=movie, per_user=[0.91, 0.84])

    @override_settings(GEMINI_API_KEY="settings-key")
    @mock.patch("apps.common.services.gemini.genai.Client")
    def test_uses_settings_api_key(self, mock_client):
        client = ComparisonNarrativeClient()

        mock_client.assert_called_once_with(api_key="settings-key")
        assert client.model == DEFAULT_MODEL

    @mock.patch("apps.common.services.gemini.genai.Client")
    def test_uses_explicit_api_key(self, mock_client):
        ComparisonNarrativeClient(api_key="explicit-key")

        mock_client.assert_called_once_with(api_key="explicit-key")

    @mock.patch.object(
        ComparisonNarrativeClient,
        "complete",
        side_effect=AIUnavailableError("Quota exceeded"),
    )
    @mock.patch("apps.common.services.gemini.genai.Client")
    def test_generate_returns_none_when_quota_is_exceeded(
        self,
        mock_client,
        mock_complete,
    ):
        client = ComparisonNarrativeClient(api_key="test-key")

        result = self._generate(client)

        assert result is None
        mock_complete.assert_called_once()
        mock_client.return_value.models.generate_content.assert_not_called()

    @mock.patch("apps.common.services.gemini.api_quota.adjust")
    @mock.patch("apps.common.services.gemini.api_quota.cost_units")
    def test_reconcile_cost_adjusts_actual_difference(
        self,
        mock_cost,
        mock_adjust,
    ):
        mock_cost.return_value = 12
        client = object.__new__(ComparisonNarrativeClient)

        response = mock.Mock(
            usage_metadata=mock.Mock(
                prompt_token_count=50,
                candidates_token_count=20,
                thoughts_token_count=5,
            ),
        )

        client._reconcile_cost(
            response,
            reserved=10,
            label="comparison narrative",
        )

        mock_cost.assert_called_once_with(
            "gemini_narrative",
            input_tokens=50,
            output_tokens=25,
        )
        mock_adjust.assert_called_once_with("gemini_narrative", 2)

    @mock.patch("apps.common.services.gemini.api_quota.adjust")
    def test_reconcile_cost_does_nothing_without_usage(self, mock_adjust):
        client = object.__new__(ComparisonNarrativeClient)
        response = mock.Mock(usage_metadata=None)

        client._reconcile_cost(
            response,
            reserved=10,
            label="comparison narrative",
        )

        mock_adjust.assert_not_called()

    @mock.patch("apps.common.services.gemini.api_quota.adjust")
    def test_reconcile_cost_does_nothing_without_prompt_count(
        self,
        mock_adjust,
    ):
        client = object.__new__(ComparisonNarrativeClient)
        response = mock.Mock(
            usage_metadata=mock.Mock(prompt_token_count=None),
        )

        client._reconcile_cost(
            response,
            reserved=10,
            label="comparison narrative",
        )

        mock_adjust.assert_not_called()

    @mock.patch.object(ComparisonNarrativeClient, "complete")
    @mock.patch("apps.common.services.gemini.genai.Client")
    def test_generate_calls_gemini_and_parses_response(
        self,
        mock_client,
        mock_complete,
    ):
        mock_complete.return_value = Completion(
            text=(
                '{"narrative":"You have similar tastes.",'
                '"individual":{'
                '"A":"This person enjoys science fiction.",'
                '"B":"This person also enjoys science fiction."},'
                '"recommendations":["Good fit."]}'
            ),
            finish_reason=None,
        )

        client = ComparisonNarrativeClient(api_key="test-key")

        result = self._generate(client, [self._candidate()])

        assert result is not None
        assert result.summary == "You have similar tastes."
        assert result.reasons == {1: "Good fit."}
        assert result.individual == {
            "1": "This person enjoys science fiction.",
            "2": "This person also enjoys science fiction.",
        }

        mock_complete.assert_called_once()
        args, kwargs = mock_complete.call_args
        assert isinstance(args[0], str)
        assert "Dune (2021)" in args[0]
        assert kwargs == {
            "max_output_tokens": _max_output_tokens(1),
            "json_output": True,
            "label": "comparison narrative",
        }
        mock_client.return_value.models.generate_content.assert_not_called()

    @mock.patch.object(ComparisonNarrativeClient, "complete")
    @mock.patch("apps.common.services.gemini.genai.Client")
    def test_generate_returns_none_for_unparseable_response(
        self,
        mock_client,
        mock_complete,
    ):
        mock_complete.return_value = Completion(
            text="not json",
            finish_reason=None,
        )

        client = ComparisonNarrativeClient(api_key="test-key")

        assert self._generate(client) is None

        mock_complete.assert_called_once()
        mock_client.return_value.models.generate_content.assert_not_called()

    @mock.patch.object(
        ComparisonNarrativeClient,
        "complete",
        side_effect=AIUnavailableError("Gemini failed"),
    )
    @mock.patch("apps.common.services.gemini.genai.Client")
    def test_generate_returns_none_on_gemini_exception(
        self,
        mock_client,
        mock_complete,
    ):
        client = ComparisonNarrativeClient(api_key="test-key")

        assert self._generate(client) is None

        mock_complete.assert_called_once()
        mock_client.return_value.models.generate_content.assert_not_called()


LABELS = {"u1": "A", "u2": "B"}
USER_IDS = ["u1", "u2"]


class TestSmallHelper:
    def test_json_is_minified_and_keeps_unicode(self):
        assert _json({"a": [1, 2], "b": "Amélie"}) == '{"a":[1,2],"b":"Amélie"}'

    def test_letters_follow_user_order(self):
        assert _letters(["x", "y", "z"]) == ["A", "B", "C"]
        assert _letters([]) == []

    def test_labels_map_user_ids_to_letters(self):
        assert _labels(["x", "y"]) == {"x": "A", "y": "B"}

    def test_fmt_ratings_uses_labels(self):
        entry = {"ratings": {"u1": 4.5, "u2": 2.0}}

        assert _fmt_ratings(entry, LABELS) == "A=4.5 vs B=2.0"

    def test_fmt_ratings_skips_unknown_users(self):
        entry = {"ratings": {"u1": 4.5, "ghost": 1.0}}

        assert _fmt_ratings(entry, LABELS) == "A=4.5"


class TestProfilesBlock:
    def test_one_line_per_known_user(self):
        internal = {
            "profiles": {
                "u1": {"mean_rating": 4.0},
                "u2": {"mean_rating": 3.0},
                "ghost": {"mean_rating": 1.0},
            }
        }

        assert _profiles_block(internal, LABELS) == 'A: {"mean_rating":4.0}\nB: {"mean_rating":3.0}'

    def test_returns_none_marker_without_profiles(self):
        assert _profiles_block({}, LABELS) == "(none)"
        assert _profiles_block({"profiles": {}}, LABELS) == "(none)"
        assert _profiles_block({"profiles": {"ghost": {}}}, LABELS) == "(none)"


class TestCandidateLine:
    def _candidate(self, *, per_user=(0.91, 0.84), genres=("Sci-Fi", "Adventure"),
                   directors=("Denis Villeneuve",), description="An epic."):
        movie = mock.Mock(
            title="Dune", release_year=2021, wikidata_description=description
        )
        movie.directors = list(directors) if directors is not None else None
        movie.genres.all.return_value = [
            SimpleNamespace(name=g) for g in genres
        ]
        return SimpleNamespace(movie=movie, per_user=list(per_user))

    def test_full_line(self):
        line = _candidate_line(1, self._candidate(), LABELS, USER_IDS)

        assert (
            line
            == "1. Dune (2021) | Sci-Fi, Adventure | dir. Denis Villeneuve"
            " | fit A=0.91 B=0.84 | An epic."
        )

    def test_only_first_two_string_directors_are_used(self):
        candidate = self._candidate(directors=["X", 5, None, "Y", "Z"])

        line = _candidate_line(1, candidate, LABELS, USER_IDS)

        assert "dir. X, Y" in line
        assert "Z" not in line

    def test_missing_directors_genres_and_description_are_omitted(self):
        candidate = self._candidate(
            directors=None, genres=(), description=None
        )

        line = _candidate_line(2, candidate, LABELS, USER_IDS)

        assert line == "2. Dune (2021) | fit A=0.91 B=0.84"

    def test_leaning_towards_first_user(self):
        candidate = self._candidate(per_user=(0.9, 0.5))

        line = _candidate_line(1, candidate, LABELS, USER_IDS)

        assert "(leans A)" in line

    def test_leaning_towards_second_user(self):
        candidate = self._candidate(per_user=(0.5, 0.9))

        line = _candidate_line(1, candidate, LABELS, USER_IDS)

        assert "(leans B)" in line

    def test_lean_threshold_is_inclusive(self):
        line = _candidate_line(
            1, self._candidate(per_user=(0.75, 0.5)), LABELS, USER_IDS
        )

        assert "(leans A)" in line

    def test_no_lean_below_threshold(self):
        line = _candidate_line(
            1, self._candidate(per_user=(0.8, 0.7)), LABELS, USER_IDS
        )

        assert "leans" not in line


class TestStoryAnglesLimit:
    def test_returns_at_most_max_angles_in_priority_order(self):
        public = {
            "taste_similarity": 0.7,
            "rating_correlation": 0.1,
            "common_count": 50,
            "library_sizes": {"u1": 100, "u2": 100},
            "divergences": [
                {"title": "Blade Runner", "ratings": {"u1": 5, "u2": 1}}
            ],
            "agreements": [
                {"title": "Alien", "ratings": {"u1": 5, "u2": 5}}
            ],
        }
        internal = {
            "profiles": {},
            "shared_directors": ["Carpenter"],
            "shared_genres": ["Horror"],
        }

        angles = _story_angles(public, internal, LABELS)

        assert len(angles) == MAX_ANGLES
        assert angles[0].startswith("Similar taste on paper")
        assert angles[1] == "Sharpest clash: Blade Runner (A=5 vs B=1)."
        assert angles[2] == "Common ground: both rated Alien very high (A=5 vs B=5)."


class TestBuildPromptExtra:
    def _prompt(self, candidates):
        public = {
            "library_sizes": {"u1": 10, "u2": 12},
            "agreements": [],
            "divergences": [],
        }
        internal = {
            "profiles": {},
            "shared_genres": [],
            "shared_directors": [],
        }
        return _build_prompt(public, internal, candidates, USER_IDS)

    def test_prompt_requests_exactly_as_many_recommendations_as_candidates(self):
        movie = mock.Mock(
            title="Dune", release_year=2021, wikidata_description=""
        )
        movie.directors = []
        movie.genres.all.return_value = []
        candidates = [
            SimpleNamespace(movie=movie, per_user=[0.5, 0.5]) for _ in range(3)
        ]

        prompt = self._prompt(candidates)

        assert "exactly 3 strings" in prompt
        assert "1. Dune (2021)" in prompt
        assert "3. Dune (2021)" in prompt

    def test_prompt_schema_has_one_individual_entry_per_user(self):
        prompt = self._prompt([])

        assert '"individual": {"A": str, "B": str}' in prompt
        assert "recommendations: an empty list" in prompt


class TestParse:
    def _payload(self, **overrides):
        data = {
            "narrative": "  A story.  ",
            "individual": {"A": " First. ", "B": "Second."},
            "recommendations": ["One.", "Two."],
        }
        data.update(overrides)
        return json.dumps(data)

    def test_parses_valid_response_and_strips_text(self):
        result = _parse(self._payload(), 2, USER_IDS)

        assert result.summary == "A story."
        assert result.individual == {"u1": "First.", "u2": "Second."}
        assert result.reasons == {1: "One.", 2: "Two."}

    def test_parses_dict_recommendations_with_explicit_index(self):
        payload = self._payload(
            recommendations=[
                {"index": 2, "reason": "Second."},
                {"index": 1, "reason": "First."},
            ]
        )

        result = _parse(payload, 2, USER_IDS)

        assert result.reasons == {1: "First.", 2: "Second."}

    def test_dict_recommendation_without_index_uses_position(self):
        payload = self._payload(recommendations=[{"reason": "Only."}])

        result = _parse(payload, 2, USER_IDS)

        assert result.reasons == {1: "Only."}

    def test_recommendations_outside_candidate_range_are_ignored(self):
        payload = self._payload(
            recommendations=[
                {"index": 0, "reason": "zero"},
                {"index": 1, "reason": "ok"},
                {"index": 3, "reason": "too high"},
            ]
        )

        result = _parse(payload, 2, USER_IDS)

        assert result.reasons == {1: "ok"}

    def test_extra_string_recommendations_are_ignored(self):
        result = _parse(self._payload(recommendations=["a", "b", "c"]), 2, USER_IDS)

        assert result.reasons == {1: "a", 2: "b"}

    def test_missing_recommendations_key_gives_empty_reasons(self):
        data = {"narrative": "S", "individual": {"A": "a", "B": "b"}}

        result = _parse(json.dumps(data), 0, USER_IDS)

        assert result.reasons == {}

    def test_invalid_json_returns_none(self):
        assert _parse("not json", 2, USER_IDS) is None
        assert _parse("", 2, USER_IDS) is None

    def test_json_that_is_not_an_object_returns_none(self):
        assert _parse("[1, 2]", 2, USER_IDS) is None

    def test_missing_narrative_returns_none(self):
        data = {"individual": {"A": "a", "B": "b"}}

        assert _parse(json.dumps(data), 0, USER_IDS) is None

    def test_blank_narrative_returns_none(self):
        assert _parse(self._payload(narrative="   "), 2, USER_IDS) is None

    def test_missing_individual_letter_returns_none(self):
        payload = self._payload(individual={"A": "only A"})

        assert _parse(payload, 2, USER_IDS) is None

    def test_blank_individual_summary_returns_none(self):
        payload = self._payload(individual={"A": "ok", "B": "  "})

        assert _parse(payload, 2, USER_IDS) is None

    def test_individual_with_wrong_type_returns_none(self):
        assert _parse(self._payload(individual=["a", "b"]), 2, USER_IDS) is None

    def test_recommendation_dict_without_reason_returns_none(self):
        payload = self._payload(recommendations=[{"index": 1}])

        assert _parse(payload, 2, USER_IDS) is None

    def test_non_numeric_recommendation_index_returns_none(self):
        payload = self._payload(
            recommendations=[{"index": "first", "reason": "x"}]
        )

        assert _parse(payload, 2, USER_IDS) is None

    def test_null_recommendations_returns_none(self):
        assert _parse(self._payload(recommendations=None), 2, USER_IDS) is None
