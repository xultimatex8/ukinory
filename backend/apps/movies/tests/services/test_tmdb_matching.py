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
