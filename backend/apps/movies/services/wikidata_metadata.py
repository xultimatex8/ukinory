from __future__ import annotations

from typing import Any, Optional

from apps.movies.services.wikidata_client import WikidataClient


DEFAULT_BATCH_SIZE = 50


_BASE_QUERY = """
SELECT ?tmdbId ?item ?itemLabel ?itemDescription
WHERE {{
  VALUES ?tmdbId {{ {tmdb_id_values} }}

  ?item wdt:P4947 ?tmdbId.

  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en,es".
    ?item rdfs:label ?itemLabel.
    ?item schema:description ?itemDescription.
  }}
}}
"""


_FACTS_QUERY = """
SELECT ?tmdbId ?publicationDate ?publicationRank
       ?duration ?durationRank
       ?languageLabel ?languageRank
WHERE {{
  VALUES ?tmdbId {{ {tmdb_id_values} }}

  ?item wdt:P4947 ?tmdbId.

  OPTIONAL {{
    ?item p:P577 ?publicationStatement.
    ?publicationStatement
      wikibase:rank ?publicationRank ;
      ps:P577 ?publicationDate.
  }}

  OPTIONAL {{
    ?item p:P2047 ?durationStatement.
    ?durationStatement
      wikibase:rank ?durationRank ;
      ps:P2047 ?duration.
  }}

  OPTIONAL {{
    ?item p:P364 ?languageStatement.
    ?languageStatement
      wikibase:rank ?languageRank ;
      ps:P364 ?language.

    ?language rdfs:label ?languageLabel.

    FILTER(LANG(?languageLabel) = "en")
  }}
}}
"""


_CREDITS_QUERY = """
SELECT ?tmdbId ?genre ?genreLabel
       ?director ?directorLabel
WHERE {{
  VALUES ?tmdbId {{ {tmdb_id_values} }}

  ?item wdt:P4947 ?tmdbId.

  OPTIONAL {{
    ?item wdt:P136 ?genre.
  }}

  OPTIONAL {{
    ?item wdt:P57 ?director.
  }}

  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en,es".
    ?genre rdfs:label ?genreLabel.
    ?director rdfs:label ?directorLabel.
  }}
}}
"""


def fetch_movies_metadata(
    client: WikidataClient,
    tmdb_ids: list[int],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[int, dict[str, Any]]:
    results: dict[int, dict[str, Any]] = {}

    for start in range(0, len(tmdb_ids), batch_size):
        chunk = tmdb_ids[start : start + batch_size]
        values = " ".join(f'"{tmdb_id}"' for tmdb_id in chunk)

        base_payload = client.sparql(
            _BASE_QUERY.format(tmdb_id_values=values)
        )

        facts_payload = client.sparql(
            _FACTS_QUERY.format(tmdb_id_values=values)
        )

        credits_payload = client.sparql(
            _CREDITS_QUERY.format(tmdb_id_values=values)
        )

        base_by_tmdb_id = _index_by_tmdb_id(
            base_payload.get("results", {}).get("bindings") or []
        )

        facts_by_tmdb_id = _index_facts(
            facts_payload.get("results", {}).get("bindings") or []
        )

        credits_by_tmdb_id = _index_credits(
            credits_payload.get("results", {}).get("bindings") or []
        )

        for tmdb_id in chunk:
            base = base_by_tmdb_id.get(tmdb_id)

            if base is None:
                continue

            facts = facts_by_tmdb_id.get(tmdb_id, {})
            credits = credits_by_tmdb_id.get(tmdb_id, {})

            results[tmdb_id] = {
                "wikidata_id": _qid_from_uri(_value(base, "item")),
                "title": _value(base, "itemLabel") or "",
                "release_year": _extract_year(
                    facts.get("publication_date")
                ),
                "wikidata_description": (
                    _value(base, "itemDescription") or ""
                ),
                "runtime": _to_int(facts.get("duration")),
                "original_language": facts.get("language", ""),
                "genres": credits.get("genres", []),
                "directors": credits.get("directors", []),
            }

    return results


def _index_by_tmdb_id(
    bindings: list[dict],
) -> dict[int, dict]:
    results: dict[int, dict] = {}

    for row in bindings:
        tmdb_id_str = _value(row, "tmdbId")

        if not tmdb_id_str:
            continue

        tmdb_id = int(tmdb_id_str)

        if tmdb_id not in results:
            results[tmdb_id] = row

    return results


def _index_facts(
    bindings: list[dict],
) -> dict[int, dict[str, Optional[str]]]:
    grouped: dict[int, list[dict]] = {}

    for row in bindings:
        tmdb_id_str = _value(row, "tmdbId")

        if not tmdb_id_str:
            continue

        tmdb_id = int(tmdb_id_str)

        grouped.setdefault(tmdb_id, []).append(row)

    results: dict[int, dict[str, Optional[str]]] = {}

    for tmdb_id, rows in grouped.items():
        results[tmdb_id] = {
            "publication_date": _select_fact(
                rows,
                value_key="publicationDate",
                rank_key="publicationRank",
                numeric=False,
            ),
            "duration": _select_fact(
                rows,
                value_key="duration",
                rank_key="durationRank",
                numeric=True,
            ),
            "language": _select_fact(
                rows,
                value_key="languageLabel",
                rank_key="languageRank",
                numeric=False,
            ) or "",
        }

    return results


def _select_fact(
    rows: list[dict],
    value_key: str,
    rank_key: str,
    numeric: bool,
) -> Optional[str]:
    candidates = []

    for row in rows:
        value = _value(row, value_key)
        rank = _value(row, rank_key)

        if not value:
            continue

        # Deprecated statements are never considered.
        if rank == "http://wikiba.se/ontology#DeprecatedRank":
            continue

        candidates.append(
            (
                _rank_priority(rank),
                value,
            )
        )

    if not candidates:
        return None

    best_rank = max(priority for priority, _ in candidates)

    best_values = [
        value
        for priority, value in candidates
        if priority == best_rank
    ]

    if numeric:
        return min(
            best_values,
            key=lambda value: float(value),
        )

    return min(best_values)


def _rank_priority(rank: Optional[str]) -> int:
    if rank == "http://wikiba.se/ontology#PreferredRank":
        return 2

    if rank == "http://wikiba.se/ontology#NormalRank":
        return 1

    return 0


def _index_credits(
    bindings: list[dict],
) -> dict[int, dict[str, list]]:
    results: dict[int, dict[str, list]] = {}

    for row in bindings:
        tmdb_id_str = _value(row, "tmdbId")

        if not tmdb_id_str:
            continue

        tmdb_id = int(tmdb_id_str)

        if tmdb_id not in results:
            results[tmdb_id] = {
                "genres": [],
                "directors": [],
                "_genre_keys": set(),
                "_director_keys": set(),
            }

        result = results[tmdb_id]

        genre_qid = _qid_from_uri(_value(row, "genre"))
        genre_name = _value(row, "genreLabel")

        if genre_qid and genre_name:
            genre_key = (genre_qid, genre_name)

            if genre_key not in result["_genre_keys"]:
                result["genres"].append(
                    {
                        "wikidata_id": genre_qid,
                        "name": genre_name,
                    }
                )
                result["_genre_keys"].add(genre_key)

        director_qid = _qid_from_uri(_value(row, "director"))
        director_name = _value(row, "directorLabel")

        if director_qid and director_name:
            director_key = (director_qid, director_name)

            if director_key not in result["_director_keys"]:
                result["directors"].append(director_name)
                result["_director_keys"].add(director_key)

    for result in results.values():
        result["genres"].sort(
            key=lambda genre: (
                genre["wikidata_id"],
                genre["name"],
            )
        )

        result["directors"].sort()

        del result["_genre_keys"]
        del result["_director_keys"]

    return results


def _value(row: dict, key: str) -> Optional[str]:
    cell = row.get(key)

    return cell.get("value") if cell else None


def _qid_from_uri(uri: Optional[str]) -> Optional[str]:
    if not uri:
        return None

    return uri.rsplit("/", 1)[-1]


def _extract_year(date_value: Optional[str]) -> Optional[int]:
    if not date_value or len(date_value) < 4:
        return None

    try:
        return int(date_value[:4])
    except ValueError:
        return None


def _to_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None

    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_pipe_list(value: Optional[str]) -> list[str]:
    if not value:
        return []

    return [v for v in value.split("|") if v]


def _parse_genres(value: Optional[str]) -> list[dict[str, str]]:
    genres = []

    for pair in _parse_pipe_list(value):
        if "::" not in pair:
            continue

        qid, name = pair.split("::", 1)

        if qid and name:
            genres.append(
                {
                    "wikidata_id": qid,
                    "name": name,
                }
            )

    return genres
