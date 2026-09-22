from __future__ import annotations

import pytest
from requests.adapters import HTTPAdapter

from apps.movies.models import Movie


@pytest.fixture
def movie(db):
    return Movie.objects.create(
        tmdb_id=12345,
        title="Test Movie",
        release_year=2020,
        wikidata_description="A test movie.",
        original_language="en",
        runtime=120,
    )
