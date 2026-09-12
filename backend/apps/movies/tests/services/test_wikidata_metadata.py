from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.movies.exceptions import WikidataNotFoundError
from apps.movies.services.wikidata_metadata import (
    DEFAULT_BATCH_SIZE,
    fetch_movies_metadata,
)


def binding(**cells) -> dict:
    """Builds one SPARQL JSON result row, e.g. {"title": {"value": "Dune"}}."""
    return {key: {"value": value} for key, value in cells.items() if value is not None}


def detail_response(*bindings: dict) -> dict:
    return {"results": {"bindings": list(bindings)}}


def make_client(*sparql_return_values):
    client = MagicMock()
    client.sparql.side_effect = list(sparql_return_values)
    return client


DUNE_FIELDS = dict(
    item="http://www.wikidata.org/entity/Q15147339",
    itemLabel="Dune",
    itemDescription="2021 film directed by Denis Villeneuve",
    publicationDate="2021-10-22T00:00:00Z",
    duration="155",
    langLabel="English",
    genres="Q471839::Science Fiction|Q188473::Adventure",
    directors="Denis Villeneuve",
)


class TestFetchMoviesMetadataBatch:
    def test_maps_each_tmdb_id_to_its_own_metadata(self):
        client = make_client(
            {
                "results": {
                    "bindings": [
                        binding(tmdbId="438631", **DUNE_FIELDS),
                        binding(
                            tmdbId="11",
                            item="http://www.wikidata.org/entity/Q2",
                            itemLabel="Star Wars",
                        ),
                    ]
                }
            }
        )

        results = fetch_movies_metadata(client, [438631, 11])

        assert set(results.keys()) == {438631, 11}
        assert results[438631]["title"] == "Dune"
        assert results[11]["title"] == "Star Wars"

    def test_rows_without_a_tmdb_id_are_skipped(self):
        client = make_client(
            {
                "results": {
                    "bindings": [
                        binding(item="http://www.wikidata.org/entity/Q1", itemLabel="No tmdb id")
                    ]
                }
            }
        )

        results = fetch_movies_metadata(client, [1])

        assert results == {}

    def test_empty_id_list_makes_no_sparql_calls(self):
        client = make_client()

        results = fetch_movies_metadata(client, [])

        assert results == {}
        client.sparql.assert_not_called()

    def test_ids_that_fit_in_one_chunk_make_a_single_sparql_call(self):
        client = make_client({"results": {"bindings": []}})

        fetch_movies_metadata(client, [438631, 11, 550])

        client.sparql.assert_called_once()

    def test_chunks_large_id_lists_across_multiple_sparql_calls(self):
        ids = list(range(1, 121))  # DEFAULT_BATCH_SIZE=50 -> 3 chunks (50/50/20)
        client = make_client(
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
        )

        fetch_movies_metadata(client, ids)

        assert client.sparql.call_count == 3

    def test_respects_a_custom_batch_size(self):
        client = make_client(
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
        )

        fetch_movies_metadata(client, [1, 2, 3, 4, 5], batch_size=2)

        assert client.sparql.call_count == 3

    def test_query_contains_every_id_in_the_chunk(self):
        client = make_client({"results": {"bindings": []}})

        fetch_movies_metadata(client, [438631, 11])

        (query,), _ = client.sparql.call_args
        assert '"438631"' in query
        assert '"11"' in query

    def test_results_across_chunks_are_merged(self):
        client = make_client(
            {
                "results": {
                    "bindings": [
                        binding(tmdbId="1", item="http://www.wikidata.org/entity/Q1")
                    ]
                }
            },
            {
                "results": {
                    "bindings": [
                        binding(tmdbId="2", item="http://www.wikidata.org/entity/Q2")
                    ]
                }
            },
        )

        results = fetch_movies_metadata(client, [1, 2], batch_size=1)

        assert set(results.keys()) == {1, 2}


def test_default_batch_size_is_reasonable():
    assert 1 < DEFAULT_BATCH_SIZE <= 200
