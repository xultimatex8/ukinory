from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from apps.movies.exceptions import TMDbNotFoundError
from apps.movies.models import Movie
from apps.movies.services import wikidata_metadata as wikidata_metadata_module
from apps.movies.services.wikidata_metadata import (
    DEFAULT_BATCH_SIZE,
    fetch_movies_metadata,
)

ENTITY_PROPS = "claims|labels|descriptions"

MINUTE = "Q7727"
SECOND = "Q11574"
HOUR = "Q25235"

DUNE_QID = "Q15147339"


@pytest.fixture(autouse=True)
def single_metadata_worker(monkeypatch):
    """fetch_movies_metadata now processes its batch_size chunks concurrently
    via a thread pool (see wikidata_metadata._METADATA_WORKERS). That's fine
    in production, but it makes the ORDER in which chunk-level get_entities
    calls land on the mock non-deterministic. None of these tests care about
    real concurrency -- they're testing the batching/dedup business logic --
    so we force a single worker here, which makes chunk processing run one
    at a time in submission order, identical to the pre-parallel behaviour
    these assertions were written against."""
    monkeypatch.setattr(wikidata_metadata_module, "_METADATA_WORKERS", 1)


def _item_claim(qid: str, rank: str = "normal") -> dict:
    return {
        "rank": rank,
        "mainsnak": {
            "snaktype": "value",
            "datavalue": {"type": "wikibase-entityid", "value": {"id": qid}},
        },
    }


def _time_claim(time_str: str, rank: str = "normal") -> dict:
    return {
        "rank": rank,
        "mainsnak": {
            "snaktype": "value",
            "datavalue": {"type": "time", "value": {"time": time_str}},
        },
    }


def _quantity_claim(amount: float, unit: str = MINUTE, rank: str = "normal") -> dict:
    return {
        "rank": rank,
        "mainsnak": {
            "snaktype": "value",
            "datavalue": {
                "type": "quantity",
                "value": {
                    "amount": f"+{amount}",
                    "unit": f"http://www.wikidata.org/entity/{unit}",
                },
            },
        },
    }


def _novalue_claim() -> dict:
    return {"rank": "normal", "mainsnak": {"snaktype": "novalue"}}


def movie_entity(
    qid: str,
    label: Optional[str] = "Dune",
    description: Optional[str] = "2021 film directed by Denis Villeneuve",
    claims: Optional[dict] = None,
    label_lang: str = "en",
) -> dict:
    entity: dict = {"id": qid, "claims": claims or {}, "labels": {}, "descriptions": {}}
    if label is not None:
        entity["labels"][label_lang] = {"language": label_lang, "value": label}
    if description is not None:
        entity["descriptions"]["en"] = {"language": "en", "value": description}
    return entity


def label_entity(qid: str, label: str) -> dict:
    return {"id": qid, "labels": {"en": {"language": "en", "value": label}}}


def dune_entity() -> dict:
    return movie_entity(
        DUNE_QID,
        claims={
            "P577": [_time_claim("+2021-10-22T00:00:00Z")],
            "P2047": [_quantity_claim(155)],
            "P364": [_item_claim("Q1860")],
            "P136": [_item_claim("Q471839")],
            "P57": [_item_claim("Q3428569")],
        },
    )


DUNE_LABELS = {
    "Q1860": label_entity("Q1860", "English"),
    "Q471839": label_entity("Q471839", "Science Fiction"),
    "Q3428569": label_entity("Q3428569", "Denis Villeneuve"),
}


def make_tmdb_client(qid_by_tmdb_id: dict[int, Optional[str]]) -> MagicMock:
    tmdb = MagicMock()

    def fake_get(path, params=None):
        tmdb_id = int(path.split("/")[2])
        if tmdb_id not in qid_by_tmdb_id:
            raise TMDbNotFoundError(f"no {path}")
        return {"id": tmdb_id, "wikidata_id": qid_by_tmdb_id[tmdb_id]}

    tmdb.get.side_effect = fake_get
    return tmdb


def make_wikidata_client(
    entities: dict[str, dict],
    labels: Optional[dict[str, dict]] = None,
    qids_by_tmdb_id: Optional[dict[int, str]] = None,
) -> MagicMock:
    client = MagicMock()
    labels = labels or {}

    def fake_get_entities(qids, props, languages=None):
        source = labels if props == "labels" else entities
        return {qid: source[qid] for qid in qids if qid in source}

    client.get_entities.side_effect = fake_get_entities

    # Defaults to "SPARQL resolved nothing", so _resolve_qids falls straight
    # through to the per-item TMDb external_ids fallback exactly like before
    # this method existed -- which is what every test below except
    # TestSparqlQidResolution actually wants to exercise. Pass
    # qids_by_tmdb_id explicitly to test the SPARQL-hit path instead.
    client.find_qids_by_tmdb_ids.return_value = dict(qids_by_tmdb_id or {})

    return client


def label_calls(client: MagicMock) -> list:
    return [c for c in client.get_entities.call_args_list if c.kwargs["props"] == "labels"]


def entity_calls(client: MagicMock) -> list:
    return [c for c in client.get_entities.call_args_list if c.kwargs["props"] == ENTITY_PROPS]


@pytest.mark.django_db
class TestFullMetadata:
    def test_builds_the_expected_dictionary(self):
        tmdb = make_tmdb_client({438631: DUNE_QID})
        wikidata = make_wikidata_client({DUNE_QID: dune_entity()}, DUNE_LABELS)

        results = fetch_movies_metadata(wikidata, [438631], tmdb_client=tmdb)

        assert results == {
            438631: {
                "wikidata_id": DUNE_QID,
                "title": "Dune",
                "release_year": 2021,
                "wikidata_description": "2021 film directed by Denis Villeneuve",
                "runtime": 155,
                "original_language": "English",
                "genres": [{"wikidata_id": "Q471839", "name": "Science Fiction"}],
                "directors": ["Denis Villeneuve"],
            }
        }

    def test_maps_each_tmdb_id_to_its_own_metadata(self):
        tmdb = make_tmdb_client({438631: DUNE_QID, 11: "Q2"})
        wikidata = make_wikidata_client(
            {DUNE_QID: dune_entity(), "Q2": movie_entity("Q2", label="Star Wars")},
            DUNE_LABELS,
        )

        results = fetch_movies_metadata(wikidata, [438631, 11], tmdb_client=tmdb)

        assert set(results) == {438631, 11}
        assert results[438631]["title"] == "Dune"
        assert results[11]["title"] == "Star Wars"
        assert results[11]["genres"] == []
        assert results[11]["directors"] == []
        assert results[11]["runtime"] is None
        assert results[11]["release_year"] is None
        assert results[11]["original_language"] == ""

    def test_requests_claims_labels_and_descriptions_for_the_movies(self):
        tmdb = make_tmdb_client({438631: DUNE_QID})
        wikidata = make_wikidata_client({DUNE_QID: dune_entity()}, DUNE_LABELS)

        fetch_movies_metadata(wikidata, [438631], tmdb_client=tmdb)

        (call,) = entity_calls(wikidata)
        assert call.args[0] == [DUNE_QID]

    def test_labels_are_requested_for_genre_director_and_language_qids(self):
        tmdb = make_tmdb_client({438631: DUNE_QID})
        wikidata = make_wikidata_client({DUNE_QID: dune_entity()}, DUNE_LABELS)

        fetch_movies_metadata(wikidata, [438631], tmdb_client=tmdb)

        (call,) = label_calls(wikidata)
        assert call.args[0] == ["Q1860", "Q3428569", "Q471839"]


@pytest.mark.django_db
class TestQidResolution:
    def test_ids_tmdb_cannot_resolve_are_absent(self):
        tmdb = make_tmdb_client(
            {438631: DUNE_QID, 998: None, 997: "not-a-qid", 996: ""}
        )
        wikidata = make_wikidata_client({DUNE_QID: dune_entity()}, DUNE_LABELS)

        results = fetch_movies_metadata(
            wikidata, [438631, 999, 998, 997, 996], tmdb_client=tmdb
        )

        assert set(results) == {438631}

    def test_no_wikidata_call_when_nothing_resolves(self):
        tmdb = make_tmdb_client({})
        wikidata = make_wikidata_client({})

        results = fetch_movies_metadata(wikidata, [1, 2], tmdb_client=tmdb)

        assert results == {}
        wikidata.get_entities.assert_not_called()

    def test_qid_missing_from_the_wikidata_response_is_skipped(self):
        tmdb = make_tmdb_client({1: "Q1", 2: "Q2"})
        wikidata = make_wikidata_client({"Q1": movie_entity("Q1", label="One")})

        results = fetch_movies_metadata(wikidata, [1, 2], tmdb_client=tmdb)

        assert set(results) == {1}

    def test_shared_qid_is_requested_once(self):
        tmdb = make_tmdb_client({1: "Q7", 2: "Q7"})
        wikidata = make_wikidata_client({"Q7": movie_entity("Q7", label="Same")})

        results = fetch_movies_metadata(wikidata, [1, 2], tmdb_client=tmdb)

        (call,) = entity_calls(wikidata)
        assert call.args[0] == ["Q7"]
        assert set(results) == {1, 2}

    def test_stored_movies_reuse_their_wikidata_id_without_calling_tmdb(self):
        Movie.objects.create(
            tmdb_id=438631, title="Dune", release_year=2021, wikidata_id=DUNE_QID
        )
        tmdb = make_tmdb_client({})
        wikidata = make_wikidata_client({DUNE_QID: dune_entity()}, DUNE_LABELS)

        results = fetch_movies_metadata(wikidata, [438631], tmdb_client=tmdb)

        tmdb.get.assert_not_called()
        assert results[438631]["wikidata_id"] == DUNE_QID

    def test_only_new_movies_are_looked_up_in_tmdb(self):
        Movie.objects.create(
            tmdb_id=438631, title="Dune", release_year=2021, wikidata_id=DUNE_QID
        )
        tmdb = make_tmdb_client({11: "Q2"})
        wikidata = make_wikidata_client(
            {DUNE_QID: dune_entity(), "Q2": movie_entity("Q2", label="Star Wars")},
            DUNE_LABELS,
        )

        results = fetch_movies_metadata(wikidata, [438631, 11], tmdb_client=tmdb)

        assert [c.args[0] for c in tmdb.get.call_args_list] == ["/movie/11/external_ids"]
        assert set(results) == {438631, 11}

    def test_stored_movie_with_an_invalid_wikidata_id_falls_back_to_tmdb(self):
        Movie.objects.create(
            tmdb_id=438631, title="Dune", release_year=2021, wikidata_id="garbage"
        )
        tmdb = make_tmdb_client({438631: DUNE_QID})
        wikidata = make_wikidata_client({DUNE_QID: dune_entity()}, DUNE_LABELS)

        results = fetch_movies_metadata(wikidata, [438631], tmdb_client=tmdb)

        tmdb.get.assert_called_once_with("/movie/438631/external_ids")
        assert results[438631]["wikidata_id"] == DUNE_QID

    def test_builds_its_own_tmdb_client_when_none_given(self):
        with patch(
            "apps.movies.services.wikidata_metadata.TMDbClient"
        ) as mock_tmdb_cls:
            mock_tmdb_cls.return_value = make_tmdb_client({})
            fetch_movies_metadata(make_wikidata_client({}), [1])

        mock_tmdb_cls.assert_called_once_with()


@pytest.mark.django_db
class TestSparqlQidResolution:
    def test_sparql_hit_resolves_without_calling_tmdb(self):
        tmdb = make_tmdb_client({})  # would raise TMDbNotFoundError if called
        wikidata = make_wikidata_client(
            {DUNE_QID: dune_entity()},
            DUNE_LABELS,
            qids_by_tmdb_id={438631: DUNE_QID},
        )

        results = fetch_movies_metadata(wikidata, [438631], tmdb_client=tmdb)

        tmdb.get.assert_not_called()
        assert results[438631]["wikidata_id"] == DUNE_QID

    def test_sparql_is_called_once_for_the_whole_id_list_not_per_batch(self):
        ids = [1, 2, 3, 4, 5]
        tmdb = make_tmdb_client({i: f"Q{i}" for i in ids})
        wikidata = make_wikidata_client(
            {f"Q{i}": movie_entity(f"Q{i}", label=f"Movie {i}") for i in ids},
            qids_by_tmdb_id={i: f"Q{i}" for i in ids},
        )

        results = fetch_movies_metadata(wikidata, ids, batch_size=2, tmdb_client=tmdb)

        assert set(results) == set(ids)
        wikidata.find_qids_by_tmdb_ids.assert_called_once()
        (call_args, _) = wikidata.find_qids_by_tmdb_ids.call_args
        assert sorted(call_args[0]) == ids
        tmdb.get.assert_not_called()

    def test_ids_the_sparql_batch_misses_still_fall_back_to_tmdb(self):
        tmdb = make_tmdb_client({11: "Q2"})
        wikidata = make_wikidata_client(
            {DUNE_QID: dune_entity(), "Q2": movie_entity("Q2", label="Star Wars")},
            DUNE_LABELS,
            qids_by_tmdb_id={438631: DUNE_QID},  # SPARQL resolves 438631 but not 11
        )

        results = fetch_movies_metadata(wikidata, [438631, 11], tmdb_client=tmdb)

        tmdb.get.assert_called_once_with("/movie/11/external_ids")
        assert set(results) == {438631, 11}

    def test_movie_cached_locally_skips_both_sparql_and_tmdb_for_that_id(self):
        Movie.objects.create(
            tmdb_id=438631, title="Dune", release_year=2021, wikidata_id=DUNE_QID
        )
        tmdb = make_tmdb_client({11: "Q2"})
        wikidata = make_wikidata_client(
            {DUNE_QID: dune_entity(), "Q2": movie_entity("Q2", label="Star Wars")},
            DUNE_LABELS,
            qids_by_tmdb_id={11: "Q2"},
        )

        fetch_movies_metadata(wikidata, [438631, 11], tmdb_client=tmdb)

        (call_args, _) = wikidata.find_qids_by_tmdb_ids.call_args
        assert call_args[0] == [11]
        tmdb.get.assert_not_called()


@pytest.mark.django_db
class TestClaimSelection:
    def _fetch(self, claims: dict, labels: Optional[dict] = None) -> dict:
        tmdb = make_tmdb_client({1: "Q1"})
        wikidata = make_wikidata_client(
            {"Q1": movie_entity("Q1", claims=claims)}, labels or {}
        )
        return fetch_movies_metadata(wikidata, [1], tmdb_client=tmdb)[1]

    def test_earliest_publication_year_wins_among_equal_ranks(self):
        result = self._fetch(
            {
                "P577": [
                    _time_claim("+2022-03-01T00:00:00Z"),
                    _time_claim("+2021-10-22T00:00:00Z"),
                ]
            }
        )

        assert result["release_year"] == 2021

    def test_preferred_rank_beats_normal(self):
        result = self._fetch(
            {
                "P577": [
                    _time_claim("+1999-01-01T00:00:00Z"),
                    _time_claim("+2001-01-01T00:00:00Z", rank="preferred"),
                ]
            }
        )

        assert result["release_year"] == 2001

    def test_deprecated_rank_is_ignored(self):
        result = self._fetch(
            {
                "P577": [
                    _time_claim("+1990-01-01T00:00:00Z", rank="deprecated"),
                    _time_claim("+2001-01-01T00:00:00Z"),
                ]
            }
        )

        assert result["release_year"] == 2001

    def test_only_deprecated_claims_means_no_value(self):
        result = self._fetch(
            {"P577": [_time_claim("+1990-01-01T00:00:00Z", rank="deprecated")]}
        )

        assert result["release_year"] is None

    def test_novalue_snaks_are_ignored(self):
        result = self._fetch({"P577": [_novalue_claim()], "P2047": [_novalue_claim()]})

        assert result["release_year"] is None
        assert result["runtime"] is None

    def test_shortest_runtime_wins_among_equal_ranks(self):
        result = self._fetch({"P2047": [_quantity_claim(190), _quantity_claim(155)]})

        assert result["runtime"] == 155

    def test_runtime_in_hours_is_converted_to_minutes(self):
        assert self._fetch({"P2047": [_quantity_claim(2, unit=HOUR)]})["runtime"] == 120

    def test_runtime_in_seconds_is_converted_to_minutes(self):
        assert (
            self._fetch({"P2047": [_quantity_claim(7200, unit=SECOND)]})["runtime"]
            == 120
        )

    def test_runtime_with_an_unknown_unit_is_discarded(self):
        assert self._fetch({"P2047": [_quantity_claim(155, unit="Q999999")]})["runtime"] is None

    def test_non_positive_runtime_is_discarded(self):
        assert self._fetch({"P2047": [_quantity_claim(0)]})["runtime"] is None

    def test_genres_are_deduplicated_and_sorted(self):
        result = self._fetch(
            {"P136": [_item_claim("Q2"), _item_claim("Q1"), _item_claim("Q1")]},
            labels={"Q1": label_entity("Q1", "Drama"), "Q2": label_entity("Q2", "Comedy")},
        )

        assert result["genres"] == [
            {"wikidata_id": "Q1", "name": "Drama"},
            {"wikidata_id": "Q2", "name": "Comedy"},
        ]

    def test_directors_are_sorted_by_name(self):
        result = self._fetch(
            {"P57": [_item_claim("Q10"), _item_claim("Q11")]},
            labels={
                "Q10": label_entity("Q10", "Zed Director"),
                "Q11": label_entity("Q11", "Abe Director"),
            },
        )

        assert result["directors"] == ["Abe Director", "Zed Director"]

    def test_related_items_without_a_label_are_dropped(self):
        result = self._fetch(
            {"P136": [_item_claim("Q1"), _item_claim("Q2")]},
            labels={"Q1": label_entity("Q1", "Drama"), "Q2": {"id": "Q2", "labels": {}}},
        )

        assert result["genres"] == [{"wikidata_id": "Q1", "name": "Drama"}]

    def test_alphabetically_first_language_is_used(self):
        result = self._fetch(
            {"P364": [_item_claim("Q1"), _item_claim("Q2")]},
            labels={"Q1": label_entity("Q1", "Spanish"), "Q2": label_entity("Q2", "English")},
        )

        assert result["original_language"] == "English"

    def test_bce_dates_give_negative_years(self):
        result = self._fetch({"P577": [_time_claim("-0044-03-15T00:00:00Z")]})

        assert result["release_year"] == -44


@pytest.mark.django_db
class TestLabelsAndDescriptions:
    def test_title_falls_back_to_spanish_when_there_is_no_english_label(self):
        tmdb = make_tmdb_client({1: "Q1"})
        wikidata = make_wikidata_client(
            {"Q1": movie_entity("Q1", label="Duna", label_lang="es")}
        )

        assert fetch_movies_metadata(wikidata, [1], tmdb_client=tmdb)[1]["title"] == "Duna"

    def test_english_label_is_preferred_over_spanish(self):
        entity = movie_entity("Q1", label="Dune")
        entity["labels"]["es"] = {"language": "es", "value": "Duna"}
        tmdb = make_tmdb_client({1: "Q1"})
        wikidata = make_wikidata_client({"Q1": entity})

        assert fetch_movies_metadata(wikidata, [1], tmdb_client=tmdb)[1]["title"] == "Dune"

    def test_missing_label_causes_movie_to_be_skipped(self):
        tmdb = make_tmdb_client({1: "Q1"})
        wikidata = make_wikidata_client(
            {"Q1": movie_entity("Q1", label=None, description=None)}
        )

        result = fetch_movies_metadata(wikidata, [1], tmdb_client=tmdb)

        assert result == {}


@pytest.mark.django_db
class TestBatching:
    def test_empty_id_list_makes_no_calls(self):
        tmdb = make_tmdb_client({})
        wikidata = make_wikidata_client({})

        assert fetch_movies_metadata(wikidata, [], tmdb_client=tmdb) == {}
        tmdb.get.assert_not_called()
        wikidata.get_entities.assert_not_called()

    def test_ids_are_split_into_batches_of_the_given_size(self):
        ids = [1, 2, 3, 4, 5]
        tmdb = make_tmdb_client({i: f"Q{i}" for i in ids})
        wikidata = make_wikidata_client(
            {f"Q{i}": movie_entity(f"Q{i}", label=f"Movie {i}") for i in ids}
        )

        results = fetch_movies_metadata(wikidata, ids, batch_size=2, tmdb_client=tmdb)

        assert set(results) == set(ids)
        assert [c.args[0] for c in entity_calls(wikidata)] == [
            ["Q1", "Q2"],
            ["Q3", "Q4"],
            ["Q5"],
        ]
        assert tmdb.get.call_count == 5

    def test_a_label_is_only_requested_once_across_batches(self):
        claims = {"P136": [_item_claim("Q471839")]}
        tmdb = make_tmdb_client({1: "Q1", 2: "Q2"})
        wikidata = make_wikidata_client(
            {
                "Q1": movie_entity("Q1", claims=claims),
                "Q2": movie_entity("Q2", claims=claims),
            },
            {"Q471839": label_entity("Q471839", "Science Fiction")},
        )

        results = fetch_movies_metadata(wikidata, [1, 2], batch_size=1, tmdb_client=tmdb)

        assert len(label_calls(wikidata)) == 1
        assert results[1]["genres"] == results[2]["genres"]
        assert results[2]["genres"][0]["name"] == "Science Fiction"

    def test_no_label_call_when_movies_have_no_related_items(self):
        tmdb = make_tmdb_client({1: "Q1"})
        wikidata = make_wikidata_client({"Q1": movie_entity("Q1")})

        fetch_movies_metadata(wikidata, [1], tmdb_client=tmdb)

        assert label_calls(wikidata) == []


def test_default_batch_size_respects_the_wbgetentities_limit():
    assert 1 < DEFAULT_BATCH_SIZE <= 50
