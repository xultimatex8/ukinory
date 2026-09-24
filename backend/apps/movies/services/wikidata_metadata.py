from __future__ import annotations

import logging
import re
from typing import Any, Optional

from apps.movies.exceptions import TMDbNotFoundError
from apps.movies.models import Movie
from apps.movies.services.tmdb_client import TMDbClient
from apps.movies.services.wikidata_client import WikidataClient

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50
LANGUAGES = ("en", "es")

_QID_RE = re.compile(r"Q\d+")

P_PUBLICATION_DATE = "P577"
P_DURATION = "P2047"
P_LANGUAGE = "P364"
P_GENRE = "P136"
P_DIRECTOR = "P57"

_UNIT_TO_MINUTES = {
    "Q7727": 1.0,
    "Q11574": 1 / 60,
    "Q25235": 60.0,
}


def fetch_movies_metadata(
    client: WikidataClient,
    tmdb_ids: list[int],
    batch_size: int = DEFAULT_BATCH_SIZE,
    tmdb_client: Optional[TMDbClient] = None,
) -> dict[int, dict[str, Any]]:
    tmdb_client = tmdb_client or TMDbClient()
    results: dict[int, dict[str, Any]] = {}

    labels: dict[str, str] = {}

    for start in range(0, len(tmdb_ids), batch_size):
        chunk = tmdb_ids[start : start + batch_size]

        qid_by_tmdb_id = _resolve_qids(tmdb_client, chunk)
        if not qid_by_tmdb_id:
            continue

        entities = client.get_entities(
            sorted(set(qid_by_tmdb_id.values())),
            props="claims|labels|descriptions",
            languages=LANGUAGES,
        )

        related_qids: set[str] = set()
        for qid in qid_by_tmdb_id.values():
            entity = entities.get(qid)
            if entity is None:
                continue
            for prop in (P_GENRE, P_DIRECTOR, P_LANGUAGE):
                related_qids.update(_item_ids(entity, prop))

        missing = sorted(related_qids - labels.keys())
        if missing:
            label_entities = client.get_entities(
                missing, props="labels", languages=LANGUAGES
            )
            for qid in missing:
                labels[qid] = _pick_label(label_entities.get(qid))

        for tmdb_id, qid in qid_by_tmdb_id.items():
            entity = entities.get(qid)
            if entity is None:
                continue
            metadata = _build_metadata(qid, entity, labels)
            if not metadata["title"]:
                logger.warning(
                    "Skipping TMDb ID %s (%s): Wikidata entity has no en/es label.",
                    tmdb_id, qid,
                )
                continue
            results[tmdb_id] = metadata

    return results


def _resolve_qids(tmdb_client: TMDbClient, tmdb_ids: list[int]) -> dict[int, str]:
    resolved: dict[int, str] = {}

    for tmdb_id, wikidata_id in Movie.objects.filter(tmdb_id__in=tmdb_ids).values_list(
        "tmdb_id", "wikidata_id"
    ):
        if wikidata_id and _QID_RE.fullmatch(wikidata_id):
            resolved[tmdb_id] = wikidata_id

    for tmdb_id in tmdb_ids:
        if tmdb_id in resolved:
            continue

        try:
            payload = tmdb_client.get(f"/movie/{tmdb_id}/external_ids")
        except TMDbNotFoundError:
            continue

        qid = str(payload.get("wikidata_id") or "").strip()
        if _QID_RE.fullmatch(qid):
            resolved[tmdb_id] = qid

    return resolved


def _build_metadata(qid: str, entity: dict, labels: dict[str, str]) -> dict[str, Any]:
    years = [
        year
        for value in _snak_values(entity, P_PUBLICATION_DATE)
        if (year := _year_from_time(value)) is not None
    ]

    runtimes = [
        minutes
        for value in _snak_values(entity, P_DURATION)
        if (minutes := _minutes(value)) is not None and minutes > 0
    ]

    language_names = [
        name
        for lang_qid in _item_ids(entity, P_LANGUAGE)
        if (name := labels.get(lang_qid))
    ]

    genre_keys = {
        (genre_qid, name)
        for genre_qid in _item_ids(entity, P_GENRE)
        if (name := labels.get(genre_qid))
    }

    director_keys = {
        (director_qid, name)
        for director_qid in _item_ids(entity, P_DIRECTOR)
        if (name := labels.get(director_qid))
    }

    return {
        "wikidata_id": entity.get("id") or qid,
        "title": _pick_label(entity),
        "release_year": min(years) if years else None,
        "wikidata_description": _pick_description(entity),
        "runtime": min(runtimes) if runtimes else None,
        "original_language": min(language_names) if language_names else "",
        "genres": [
            {"wikidata_id": genre_qid, "name": name}
            for genre_qid, name in sorted(genre_keys)
        ],
        "directors": sorted(name for _, name in director_keys),
    }


def _best_statements(entity: dict, prop: str) -> list[dict]:
    statements = (entity.get("claims") or {}).get(prop) or []
    usable = [s for s in statements if s.get("rank") != "deprecated"]
    preferred = [s for s in usable if s.get("rank") == "preferred"]
    return preferred or usable


def _snak_values(entity: dict, prop: str) -> list[Any]:
    values = []
    for statement in _best_statements(entity, prop):
        snak = statement.get("mainsnak") or {}
        if snak.get("snaktype") != "value":
            continue
        value = (snak.get("datavalue") or {}).get("value")
        if value is not None:
            values.append(value)
    return values


def _item_ids(entity: dict, prop: str) -> list[str]:
    return [
        value["id"]
        for value in _snak_values(entity, prop)
        if isinstance(value, dict) and "id" in value
    ]


def _year_from_time(value: Any) -> Optional[int]:
    time_str = value.get("time") if isinstance(value, dict) else None
    if not time_str:
        return None

    sign = -1 if time_str.startswith("-") else 1
    digits = time_str.lstrip("+-").split("-", 1)[0]

    try:
        return sign * int(digits)
    except ValueError:
        return None


def _minutes(value: Any) -> Optional[int]:
    if not isinstance(value, dict):
        return None

    unit = value.get("unit") or ""
    factor = _UNIT_TO_MINUTES.get(unit.rsplit("/", 1)[-1])
    if factor is None:
        return None

    try:
        return int(float(value.get("amount")) * factor)
    except (TypeError, ValueError):
        return None


def _pick_label(entity: Optional[dict]) -> str:
    if not entity:
        return ""
    labels = entity.get("labels") or {}
    for lang in LANGUAGES:
        value = (labels.get(lang) or {}).get("value")
        if value:
            return value
    return ""


def _pick_description(entity: Optional[dict]) -> str:
    if not entity:
        return ""
    descriptions = entity.get("descriptions") or {}
    for lang in LANGUAGES:
        value = (descriptions.get(lang) or {}).get("value")
        if value:
            return value
    return ""
