from __future__ import annotations

from unittest.mock import MagicMock

from apps.movies.services.wikidata_metadata import (
    DEFAULT_BATCH_SIZE,
    fetch_movies_metadata,
)


def binding(**cells) -> dict:
    return {key: {"value": value} for key, value in cells.items() if value is not None}


def detail_response(*bindings: dict) -> dict:
    return {"results": {"bindings": list(bindings)}}


def make_client(*sparql_return_values):
    client = MagicMock()
    client.sparql.side_effect = list(sparql_return_values)
    return client


BASE_DUNE_FIELDS = dict(
    item="http://www.wikidata.org/entity/Q15147339",
    itemLabel="Dune",
    itemDescription="2021 film directed by Denis Villeneuve",
)


FACTS_DUNE_FIELDS = dict(
    publicationDate="2021-10-22T00:00:00Z",
    duration="155",
    language="http://www.wikidata.org/entity/Q1860",
    languageLabel="English",
)


CREDITS_DUNE_FIELDS = dict(
    genre="Q471839",
    genreLabel="Science Fiction",
    director="http://www.wikidata.org/entity/Q3428569",
    directorLabel="Denis Villeneuve",
)


class TestFetchMoviesMetadataBatch:
    def test_maps_each_tmdb_id_to_its_own_metadata(self):
        client = make_client(
            {
                "results": {
                    "bindings": [
                        binding(
                            tmdbId="438631",
                            **BASE_DUNE_FIELDS,
                        ),
                        binding(
                            tmdbId="11",
                            item="http://www.wikidata.org/entity/Q2",
                            itemLabel="Star Wars",
                        ),
                    ]
                }
            },
            {
                "results": {
                    "bindings": [
                        binding(
                            tmdbId="438631",
                            **FACTS_DUNE_FIELDS,
                        ),
                    ]
                }
            },
            {
                "results": {
                    "bindings": [
                        binding(
                            tmdbId="438631",
                            genre="Q471839",
                            genreLabel="Science Fiction",
                            director="http://www.wikidata.org/entity/Q3428569",
                            directorLabel="Denis Villeneuve",
                        ),
                    ]
                }
            },
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
                        binding(
                            item="http://www.wikidata.org/entity/Q1",
                            itemLabel="No tmdb id",
                        )
                    ]
                }
            },
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
        )

        results = fetch_movies_metadata(client, [1])

        assert results == {}

    def test_empty_id_list_makes_no_sparql_calls(self):
        client = make_client()

        results = fetch_movies_metadata(client, [])

        assert results == {}
        client.sparql.assert_not_called()

    def test_ids_that_fit_in_one_chunk_make_three_sparql_calls(self):
        client = make_client(
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
        )

        fetch_movies_metadata(client, [438631, 11, 550])

        assert client.sparql.call_count == 3

    def test_chunks_large_id_lists_across_multiple_sparql_calls(self):
        ids = list(range(1, 121))
        expected_batches = (len(ids) + DEFAULT_BATCH_SIZE - 1) // DEFAULT_BATCH_SIZE
        expected_calls = expected_batches * 3

        client = make_client(
            *(
                {"results": {"bindings": []}}
                for _ in range(expected_calls)
            )
        )

        fetch_movies_metadata(client, ids)

        assert client.sparql.call_count == expected_calls

    def test_respects_a_custom_batch_size(self):
        client = make_client(
            *(
                {"results": {"bindings": []}}
                for _ in range(9)
            )
        )

        fetch_movies_metadata(client, [1, 2, 3, 4, 5], batch_size=2)

        assert client.sparql.call_count == 9

    def test_query_contains_every_id_in_the_chunk(self):
        client = make_client(
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
        )

        fetch_movies_metadata(client, [438631, 11])

        assert client.sparql.call_count == 3

        for call in client.sparql.call_args_list:
            query = call.args[0]
            assert '"438631"' in query
            assert '"11"' in query

    def test_results_across_chunks_are_merged(self):
        client = make_client(
            {
                "results": {
                    "bindings": [
                        binding(
                            tmdbId="1",
                            item="http://www.wikidata.org/entity/Q1",
                            itemLabel="Movie 1",
                        )
                    ]
                }
            },
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
            {
                "results": {
                    "bindings": [
                        binding(
                            tmdbId="2",
                            item="http://www.wikidata.org/entity/Q2",
                            itemLabel="Movie 2",
                        )
                    ]
                }
            },
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
        )

        results = fetch_movies_metadata(client, [1, 2], batch_size=1)

        assert set(results.keys()) == {1, 2}


def test_default_batch_size_is_reasonable():
    assert 1 < DEFAULT_BATCH_SIZE <= 200
