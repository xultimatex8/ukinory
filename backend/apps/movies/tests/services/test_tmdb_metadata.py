from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.movies.exceptions import TMDbError, TMDbNotFoundError
from apps.movies.services.tmdb_metadata import (
    CARD_POSTER_SIZE,
    POSTER_MAX_RETRIES,
    POSTER_SIZE,
    POSTER_TIMEOUT_SECONDS,
    _poster_url,
    fetch_card_metadata,
    fetch_card_metadata_bulk,
    fetch_live_display_metadata,
)


def make_client(details: dict):
    client = MagicMock()
    client.get.return_value = details
    return client


def base_details(**overrides) -> dict:
    details = {
        "id": 438631,
        "title": "Dune",
        "release_date": "2021-10-22",
        "overview": "Paul Atreides unites with Chani...",
        "poster_path": "/d5NXSklXo0qyIYkgV94XAgMIckC.jpg",
        "vote_average": 8.0,
        "runtime": 155,
        "genres": [{"id": 878, "name": "Science Fiction"}, {"id": 12, "name": "Adventure"}],
        "watch/providers": {"results": {"US": {"flatrate": [{"provider_name": "Max"}]}}},
    }
    details.update(overrides)
    return details


class TestFetchMovieMetadata:
    def test_maps_basic_fields(self):
        client = make_client(base_details())

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["tmdb_id"] == 438631
        assert metadata["title"] == "Dune"
        assert metadata["release_year"] == 2021
        assert metadata["synopsis"].startswith("Paul Atreides")
        assert metadata["vote_average"] == 8.0
        assert metadata["runtime"] == 155

    def test_builds_full_poster_url(self):
        client = make_client(base_details())

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["poster_url"] == (
            "https://image.tmdb.org/t/p/w500/d5NXSklXo0qyIYkgV94XAgMIckC.jpg"
        )

    def test_missing_poster_path_gives_empty_url(self):
        client = make_client(base_details(poster_path=None))

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["poster_url"] == ""

    def test_missing_overview_gives_empty_synopsis(self):
        client = make_client(base_details(overview=None))

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["synopsis"] == ""

    def test_maps_genres(self):
        client = make_client(base_details())

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["genres"] == [
            {"tmdb_id": 878, "name": "Science Fiction"},
            {"tmdb_id": 12, "name": "Adventure"},
        ]

    def test_missing_genres_gives_empty_list(self):
        client = make_client(base_details(genres=None))

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["genres"] == []

    def test_extracts_watch_providers_results(self):
        client = make_client(base_details())

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["streaming_providers"] == {
            "US": {"flatrate": [{"provider_name": "Max"}]}
        }

    def test_missing_watch_providers_gives_empty_dict(self):
        client = make_client(base_details(**{"watch/providers": None}))

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["streaming_providers"] == {}

    def test_requests_append_to_response_watch_providers(self):
        client = make_client(base_details())

        fetch_live_display_metadata(client, 438631)

        args, kwargs = client.get.call_args
        assert args[0] == "/movie/438631"
        assert kwargs["params"]["append_to_response"] == "watch/providers"

    def test_missing_release_date_gives_none_year(self):
        client = make_client(base_details(release_date=None))

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["release_year"] is None

    def test_missing_title_gives_an_empty_string(self):
        client = make_client(base_details(title=None))

        assert fetch_live_display_metadata(client, 438631)["title"] == ""

    def test_missing_optional_numbers_give_none(self):
        details = base_details()
        del details["vote_average"]
        del details["runtime"]
        client = make_client(details)

        metadata = fetch_live_display_metadata(client, 438631)

        assert metadata["vote_average"] is None
        assert metadata["runtime"] is None

    def test_provider_payload_without_results_gives_empty_dict(self):
        client = make_client(base_details(**{"watch/providers": {"results": None}}))

        assert fetch_live_display_metadata(client, 438631)["streaming_providers"] == {}

    def test_missing_watch_providers_key_gives_empty_dict(self):
        details = base_details()
        del details["watch/providers"]
        client = make_client(details)

        assert fetch_live_display_metadata(client, 438631)["streaming_providers"] == {}

    def test_the_tmdb_id_comes_from_the_response(self):
        client = make_client(base_details(id=999))

        assert fetch_live_display_metadata(client, 438631)["tmdb_id"] == 999

    def test_tmdb_errors_are_not_swallowed(self):
        client = MagicMock()
        client.get.side_effect = TMDbNotFoundError("no movie")

        with pytest.raises(TMDbNotFoundError):
            fetch_live_display_metadata(client, 1)


class TestPosterUrl:
    def test_uses_the_large_size_by_default(self):
        assert _poster_url("/abc.jpg") == f"https://image.tmdb.org/t/p/{POSTER_SIZE}/abc.jpg"

    def test_size_can_be_chosen(self):
        assert _poster_url("/abc.jpg", "w92") == "https://image.tmdb.org/t/p/w92/abc.jpg"

    @pytest.mark.parametrize("path", [None, ""])
    def test_missing_path_gives_an_empty_url(self, path):
        assert _poster_url(path) == ""

    def test_card_size_is_smaller_than_the_default_one(self):
        assert int(CARD_POSTER_SIZE[1:]) < int(POSTER_SIZE[1:])


class TestFetchCardMetadata:
    def test_maps_the_card_fields(self):
        client = make_client(base_details())

        assert fetch_card_metadata(client, 438631) == {
            "title": "Dune",
            "release_year": 2021,
            "poster_url": f"https://image.tmdb.org/t/p/{CARD_POSTER_SIZE}/d5NXSklXo0qyIYkgV94XAgMIckC.jpg",
            "genres": ["Science Fiction", "Adventure"],
        }

    def test_requests_the_movie_without_extra_parameters(self):
        client = make_client(base_details())

        fetch_card_metadata(client, 438631)

        client.get.assert_called_once_with("/movie/438631")

    def test_poster_size_can_be_chosen(self):
        client = make_client(base_details())

        metadata = fetch_card_metadata(client, 438631, size="w185")

        assert "/w185/" in metadata["poster_url"]

    def test_missing_fields_give_empty_values(self):
        client = make_client({"id": 1, "title": None, "release_date": None,
                              "poster_path": None, "genres": None})

        assert fetch_card_metadata(client, 1) == {
            "title": "",
            "release_year": None,
            "poster_url": "",
            "genres": [],
        }

    def test_tmdb_errors_are_not_swallowed(self):
        client = MagicMock()
        client.get.side_effect = TMDbError("boom")

        with pytest.raises(TMDbError):
            fetch_card_metadata(client, 1)


class TestFetchCardMetadataBulk:
    def details_client(self, details_by_id):
        client = MagicMock()

        def get(path, params=None):
            tmdb_id = int(path.rsplit("/", 1)[-1])
            result = details_by_id[tmdb_id]
            if isinstance(result, Exception):
                raise result
            return result

        client.get.side_effect = get
        return client

    def test_empty_input_returns_empty_dict_without_building_a_client(self):
        with patch("apps.movies.services.tmdb_metadata.TMDbClient") as client_cls:
            assert fetch_card_metadata_bulk([]) == {}

        client_cls.assert_not_called()

    def test_returns_the_metadata_of_every_id(self):
        client = self.details_client({
            1: base_details(id=1, title="One"),
            2: base_details(id=2, title="Two"),
        })

        result = fetch_card_metadata_bulk([1, 2], client=client)

        assert set(result) == {1, 2}
        assert result[1]["title"] == "One"
        assert result[2]["title"] == "Two"

    def test_duplicated_ids_are_requested_once(self):
        client = self.details_client({1: base_details(id=1)})

        fetch_card_metadata_bulk([1, 1, 1], client=client)

        assert client.get.call_count == 1

    def test_accepts_any_iterable(self):
        client = self.details_client({1: base_details(id=1), 2: base_details(id=2)})

        result = fetch_card_metadata_bulk((i for i in (1, 2)), client=client)

        assert set(result) == {1, 2}

    def test_ids_that_tmdb_rejects_are_left_out(self, caplog):
        client = self.details_client({
            1: base_details(id=1),
            2: TMDbNotFoundError("gone"),
        })

        with caplog.at_level("INFO"):
            result = fetch_card_metadata_bulk([1, 2], client=client)

        assert set(result) == {1}
        assert "No TMDb metadata for tmdb_id=2" in caplog.text

    def test_the_poster_size_is_applied_to_every_movie(self):
        client = self.details_client({1: base_details(id=1)})

        result = fetch_card_metadata_bulk([1], size="w185", client=client)

        assert "/w185/" in result[1]["poster_url"]

    def test_unexpected_errors_are_not_swallowed(self):
        client = self.details_client({1: RuntimeError("bug")})

        with pytest.raises(RuntimeError, match="bug"):
            fetch_card_metadata_bulk([1], client=client)

    def test_builds_a_fast_failing_client_when_none_is_given(self):
        with patch("apps.movies.services.tmdb_metadata.TMDbClient") as client_cls:
            client_cls.return_value = self.details_client({1: base_details(id=1)})
            result = fetch_card_metadata_bulk([1])

        client_cls.assert_called_once_with(
            max_retries=POSTER_MAX_RETRIES, timeout=POSTER_TIMEOUT_SECONDS
        )
        assert set(result) == {1}

    def test_returns_nothing_when_the_client_cannot_be_built(self, caplog):
        with patch(
            "apps.movies.services.tmdb_metadata.TMDbClient",
            side_effect=TMDbError("no key"),
        ), caplog.at_level("WARNING"):
            result = fetch_card_metadata_bulk([1, 2])

        assert result == {}
        assert "TMDb client unavailable" in caplog.text

    def test_a_given_client_is_used_instead_of_building_one(self):
        client = self.details_client({1: base_details(id=1)})

        with patch("apps.movies.services.tmdb_metadata.TMDbClient") as client_cls:
            fetch_card_metadata_bulk([1], client=client)

        client_cls.assert_not_called()
