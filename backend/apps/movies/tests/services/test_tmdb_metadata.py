from __future__ import annotations

from unittest.mock import MagicMock

from apps.movies.services.tmdb_metadata import fetch_movie_metadata


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

        metadata = fetch_movie_metadata(client, 438631)

        assert metadata["tmdb_id"] == 438631
        assert metadata["title"] == "Dune"
        assert metadata["release_year"] == 2021
        assert metadata["synopsis"].startswith("Paul Atreides")
        assert metadata["vote_average"] == 8.0
        assert metadata["runtime"] == 155

    def test_builds_full_poster_url(self):
        client = make_client(base_details())

        metadata = fetch_movie_metadata(client, 438631)

        assert metadata["poster_url"] == (
            "https://image.tmdb.org/t/p/w500/d5NXSklXo0qyIYkgV94XAgMIckC.jpg"
        )

    def test_missing_poster_path_gives_empty_url(self):
        client = make_client(base_details(poster_path=None))

        metadata = fetch_movie_metadata(client, 438631)

        assert metadata["poster_url"] == ""

    def test_missing_overview_gives_empty_synopsis(self):
        client = make_client(base_details(overview=None))

        metadata = fetch_movie_metadata(client, 438631)

        assert metadata["synopsis"] == ""

    def test_maps_genres(self):
        client = make_client(base_details())

        metadata = fetch_movie_metadata(client, 438631)

        assert metadata["genres"] == [
            {"tmdb_id": 878, "name": "Science Fiction"},
            {"tmdb_id": 12, "name": "Adventure"},
        ]

    def test_missing_genres_gives_empty_list(self):
        client = make_client(base_details(genres=None))

        metadata = fetch_movie_metadata(client, 438631)

        assert metadata["genres"] == []

    def test_extracts_watch_providers_results(self):
        client = make_client(base_details())

        metadata = fetch_movie_metadata(client, 438631)

        assert metadata["streaming_providers"] == {
            "US": {"flatrate": [{"provider_name": "Max"}]}
        }

    def test_missing_watch_providers_gives_empty_dict(self):
        client = make_client(base_details(**{"watch/providers": None}))

        metadata = fetch_movie_metadata(client, 438631)

        assert metadata["streaming_providers"] == {}

    def test_requests_append_to_response_watch_providers(self):
        client = make_client(base_details())

        fetch_movie_metadata(client, 438631)

        args, kwargs = client.get.call_args
        assert args[0] == "/movie/438631"
        assert kwargs["params"]["append_to_response"] == "watch/providers"

    def test_missing_release_date_gives_none_year(self):
        client = make_client(base_details(release_date=None))

        metadata = fetch_movie_metadata(client, 438631)

        assert metadata["release_year"] is None
