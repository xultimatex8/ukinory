from __future__ import annotations

from typing import Any, Optional

from apps.movies.services.wikidata_client import WikidataClient


DEFAULT_BATCH_SIZE = 50


_BATCH_QUERY = """
SELECT ?tmdbId ?item ?itemLabel ?itemDescription ?publicationDate ?duration ?langLabel
       (GROUP_CONCAT(DISTINCT ?genrePair; separator="|") AS ?genres)
       (GROUP_CONCAT(DISTINCT ?directorLabel; separator="|") AS ?directors)
WHERE {{
  VALUES ?tmdbId {{ {tmdb_id_values} }}
  ?item wdt:P4947 ?tmdbId.

  OPTIONAL {{ ?item wdt:P577 ?publicationDate. }}
  OPTIONAL {{ ?item wdt:P2047 ?duration. }}
  OPTIONAL {{ ?item wdt:P364 ?lang. }}

  OPTIONAL {{
    ?item wdt:P136 ?genre.
    BIND(STRAFTER(STR(?genre), "/entity/") AS ?genreQid)
  }}

  OPTIONAL {{ ?item wdt:P57 ?director. }}

  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en,es".
    ?item rdfs:label ?itemLabel.
    ?item schema:description ?itemDescription.
    ?genre rdfs:label ?genreLabel.
    ?director rdfs:label ?directorLabel.
    ?lang rdfs:label ?langLabel.
  }}

  BIND(IF(BOUND(?genreQid) && BOUND(?genreLabel),
          CONCAT(?genreQid, "::", ?genreLabel), "") AS ?genrePair)
}}
GROUP BY ?tmdbId ?item ?itemLabel ?itemDescription ?publicationDate ?duration ?langLabel
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

        payload = client.sparql(
            _BATCH_QUERY.format(tmdb_id_values=values)
        )
        bindings = payload.get("results", {}).get("bindings") or []

        for row in bindings:
            tmdb_id_str = _value(row, "tmdbId")

            if not tmdb_id_str:
                continue

            results[int(tmdb_id_str)] = _row_to_metadata(row)

    return results


def _row_to_metadata(row: dict) -> dict[str, Any]:
    return {
        "wikidata_id": _qid_from_uri(_value(row, "item")),
        "title": _value(row, "itemLabel") or "",
        "release_year": _extract_year(_value(row, "publicationDate")),
        "wikidata_description": _value(row, "itemDescription") or "",
        "runtime": _to_int(_value(row, "duration")),
        "original_language": _value(row, "langLabel") or "",
        "genres": _parse_genres(_value(row, "genres")),
        "directors": _parse_pipe_list(_value(row, "directors")),
    }


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
            genres.append({
                "wikidata_id": qid,
                "name": name,
            })

    return genres
