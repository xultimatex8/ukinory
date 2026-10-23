from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.movies.exceptions import MovieMatchNotFound
from apps.movies.services.tmdb_matching import _normalize_title, match_movie


def make_client(*get_return_values):
    client = MagicMock()
    client.get.side_effect = get_return_values
    return client


def result(tmdb_id, title, release_date=None, popularity=0.0):
    return {
        "id": tmdb_id,
        "title": title,
        "release_date": release_date,
        "popularity": popularity,
    }


class TestNormalizeTitle:
    def test_lowercases(self):
        assert _normalize_title("Dune") == "dune"

    def test_strips_punctuation_and_spaces(self):
        assert _normalize_title("Dune: Part Two") == _normalize_title("dune parttwo")

    def test_is_consistent_regardless_of_casing(self):
        assert _normalize_title("ALIEN") == _normalize_title("alien")


class TestMatchMovieHappyPath:
    def test_single_result_within_year_matches(self):
        client = make_client({"results": [result(1, "Dune", "2021-10-22", 100.0)]})

        match = match_movie(client, "Dune", 2021)

        assert match.tmdb_id == 1
        assert match.release_year == 2021
        assert match.is_ambiguous is False

    def test_matches_within_year_tolerance(self):
        client = make_client({"results": [result(1, "Dune", "2021-10-22", 100.0)]})

        match = match_movie(client, "Dune", 2020)

        assert match.tmdb_id == 1

    def test_falls_back_to_unconstrained_search_when_year_constrained_is_empty(self):
        client = make_client(
            {"results": []},
            {"results": [result(1, "Dune", "2021-10-22", 100.0)]},
        )

        match = match_movie(client, "Dune", 2021)

        assert match.tmdb_id == 1
        assert client.get.call_count == 2

    def test_picks_highest_popularity_among_exact_title_matches(self):
        client = make_client(
            {
                "results": [
                    result(1, "Dune", "2021-10-22", 50.0),
                    result(2, "Dune", "2021-10-22", 200.0),
                ]
            }
        )

        match = match_movie(client, "Dune", 2021)

        assert match.tmdb_id == 2

    def test_prefers_exact_title_over_fuzzy_match_in_same_year(self):
        client = make_client(
            {
                "results": [
                    result(1, "Dune: Part One", "2021-10-22", 999.0),
                    result(2, "Dune", "2021-10-22", 10.0),
                ]
            }
        )

        match = match_movie(client, "Dune", 2021)

        assert match.tmdb_id == 2

    def test_flags_ambiguous_when_multiple_candidates_remain(self):
        client = make_client(
            {
                "results": [
                    result(1, "Alien", "1979-05-25", 10.0),
                    result(2, "Alien", "1979-06-22", 20.0),
                ]
            }
        )

        match = match_movie(client, "Alien", 1979)

        assert match.is_ambiguous is True
        assert match.tmdb_id == 2

    def test_unambiguous_when_only_one_candidate_survives_filtering(self):
        client = make_client(
            {
                "results": [
                    result(1, "Alien", "1979-05-25", 10.0),
                    result(2, "Alien 3", "1992-05-22", 999.0),
                ]
            }
        )

        match = match_movie(client, "Alien", 1979)

        assert match.is_ambiguous is False
        assert match.tmdb_id == 1


class TestMatchMovieNotFound:
    def test_no_results_at_all_raises(self):
        client = make_client({"results": []}, {"results": []})
 
        with pytest.raises(MovieMatchNotFound):
            match_movie(client, "Some Obscure Short Film", 2021)
 
    def test_no_year_and_empty_results_raises(self):
        client = make_client({"results": []})
 
        with pytest.raises(MovieMatchNotFound):
            match_movie(client, "Nonexistent", None)
 
    def test_exception_carries_title_and_year(self):
        client = make_client({"results": []}, {"results": []})
 
        with pytest.raises(MovieMatchNotFound) as exc_info:
            match_movie(client, "Nonexistent", 2021)
 
        assert exc_info.value.title == "Nonexistent"
        assert exc_info.value.year == 2021


class TestMatchMovieNoYear:
    def test_matches_without_year_constraint(self):
        client = make_client({"results": [result(1, "Dune", "2021-10-22", 100.0)]})

        match = match_movie(client, "Dune", None)

        assert match.tmdb_id == 1

    def test_search_params_omit_primary_release_year_when_year_is_none(self):
        client = make_client({"results": [result(1, "Dune", "2021-10-22")]})

        match_movie(client, "Dune", None)

        _, kwargs = client.get.call_args
        assert "primary_release_year" not in kwargs["params"]

    def test_search_params_include_primary_release_year_when_given(self):
        client = make_client({"results": [result(1, "Dune", "2021-10-22")]})

        match_movie(client, "Dune", 2021)

        _, kwargs = client.get.call_args
        assert kwargs["params"]["primary_release_year"] == 2021


class TestNormalizeTitleDetails:
    def test_keeps_digits(self):
        assert _normalize_title("Se7en") == "se7en"

    def test_an_empty_title_normalises_to_an_empty_string(self):
        assert _normalize_title("") == ""

    def test_only_punctuation_normalises_to_an_empty_string(self):
        assert _normalize_title("...!?") == ""


class TestMatchMovieSearch:
    def test_searches_the_movie_endpoint_without_adult_content(self):
        client = make_client({"results": [result(1, "Dune", "2021-10-22")]})

        match_movie(client, "Dune", 2021)

        args, kwargs = client.get.call_args
        assert args[0] == "/search/movie"
        assert kwargs["params"]["query"] == "Dune"
        assert kwargs["params"]["include_adult"] == "false"

    def test_the_fallback_search_drops_the_year(self):
        client = make_client({"results": []}, {"results": [result(1, "Dune", "2021-10-22")]})

        match_movie(client, "Dune", 2021)

        first, second = client.get.call_args_list
        assert first.kwargs["params"]["primary_release_year"] == 2021
        assert "primary_release_year" not in second.kwargs["params"]

    def test_no_fallback_without_a_year(self):
        client = make_client({"results": []})

        with pytest.raises(MovieMatchNotFound):
            match_movie(client, "Nothing", None)

        assert client.get.call_count == 1

    def test_no_fallback_when_the_first_search_already_has_results(self):
        client = make_client({"results": [result(1, "Dune", "1984-12-14")]})

        match = match_movie(client, "Dune", 2021)

        assert client.get.call_count == 1
        assert match.tmdb_id == 1

    def test_a_payload_without_results_counts_as_empty(self):
        client = make_client({}, {})

        with pytest.raises(MovieMatchNotFound):
            match_movie(client, "Dune", 2021)


class TestMatchMovieSelection:
    def test_movies_outside_the_year_tolerance_lose_to_one_inside_it(self):
        client = make_client(
            {
                "results": [
                    result(1, "Dune", "2019-01-01", 999.0),
                    result(2, "Dune", "2021-10-22", 1.0),
                ]
            }
        )

        assert match_movie(client, "Dune", 2021).tmdb_id == 2

    def test_when_nothing_is_within_tolerance_the_best_overall_is_used(self):
        client = make_client({"results": [result(1, "Dune", "1984-12-14", 5.0)]})

        match = match_movie(client, "Dune", 2021)

        assert match.tmdb_id == 1
        assert match.release_year == 1984

    def test_a_result_without_a_release_date_is_never_within_tolerance(self):
        client = make_client(
            {
                "results": [
                    result(1, "Dune", None, 999.0),
                    result(2, "Dune", "2021-10-22", 1.0),
                ]
            }
        )

        assert match_movie(client, "Dune", 2021).tmdb_id == 2

    def test_a_lone_result_without_a_release_date_is_still_matched(self):
        client = make_client({"results": [result(1, "Dune", None, 3.0)]})

        match = match_movie(client, "Dune", 2021)

        assert match.tmdb_id == 1
        assert match.release_year is None

    def test_without_a_year_the_exact_title_still_wins(self):
        client = make_client(
            {
                "results": [
                    result(1, "Dune: Part Two", "2024-02-27", 999.0),
                    result(2, "Dune", "2021-10-22", 1.0),
                ]
            }
        )

        assert match_movie(client, "Dune", None).tmdb_id == 2

    def test_titles_are_compared_ignoring_case_and_punctuation(self):
        client = make_client(
            {
                "results": [
                    result(1, "Dune: Part Two", "2024-02-27", 1.0),
                    result(2, "Dune Part Two Making Of", "2024-03-01", 999.0),
                ]
            }
        )

        assert match_movie(client, "dune part two", 2024).tmdb_id == 1

    def test_missing_popularity_counts_as_zero(self):
        client = make_client(
            {
                "results": [
                    {"id": 1, "title": "Dune", "release_date": "2021-10-22", "popularity": None},
                    result(2, "Dune", "2021-10-22", 0.5),
                ]
            }
        )

        match = match_movie(client, "Dune", 2021)

        assert match.tmdb_id == 2

    def test_equal_popularity_keeps_the_first_result(self):
        client = make_client(
            {
                "results": [
                    result(1, "Dune", "2021-10-22", 10.0),
                    result(2, "Dune", "2021-10-22", 10.0),
                ]
            }
        )

        assert match_movie(client, "Dune", 2021).tmdb_id == 1

    def test_the_match_carries_tmdb_title_year_and_popularity(self):
        client = make_client({"results": [result(7, "Dune (2021)", "2021-10-22", 42.5)]})

        match = match_movie(client, "dune", 2021)

        assert (match.tmdb_id, match.title, match.release_year, match.popularity) == (
            7, "Dune (2021)", 2021, 42.5,
        )

    def test_the_requested_title_is_used_when_tmdb_has_none(self):
        client = make_client(
            {"results": [{"id": 7, "release_date": "2021-10-22", "popularity": 1.0}]}
        )

        assert match_movie(client, "Dune", 2021).title == "Dune"

    def test_ambiguity_is_logged_with_the_chosen_id(self, caplog):
        client = make_client(
            {
                "results": [
                    result(1, "Alien", "1979-05-25", 10.0),
                    result(2, "Alien", "1979-06-22", 20.0),
                ]
            }
        )

        with caplog.at_level("INFO"):
            match_movie(client, "Alien", 1979)

        assert "Ambiguous TMDb match for 'Alien' (1979)" in caplog.text
        assert "picked tmdb_id=2" in caplog.text

    def test_a_clear_match_is_not_logged_as_ambiguous(self, caplog):
        client = make_client({"results": [result(1, "Alien", "1979-05-25", 10.0)]})

        with caplog.at_level("INFO"):
            match_movie(client, "Alien", 1979)

        assert "Ambiguous" not in caplog.text
