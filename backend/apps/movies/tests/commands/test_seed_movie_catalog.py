from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.movies.exceptions import TMDbError
from apps.movies.services.catalog_seeding import CatalogSeedSummary

FAKE_SUMMARY = CatalogSeedSummary(
    discovered=10, stored=8, without_metadata=2, pool_sizes={"popular": 10}
)


class TestSeedMovieCatalogFullCommand:
    TARGET = "apps.movies.management.commands.seed_movie_catalog.seed_movie_catalog"

    def test_prints_summary_on_success(self):
        with patch(self.TARGET, return_value=FAKE_SUMMARY):
            out = StringIO()
            call_command("seed_movie_catalog", stdout=out)

        assert "Discovered 10" in out.getvalue()

    def test_propagates_and_reports_tmdb_errors(self):
        with patch(self.TARGET, side_effect=TMDbError("boom")):
            err = StringIO()
            with pytest.raises(TMDbError):
                call_command("seed_movie_catalog", stderr=err)

        assert "Catalog seeding failed" in err.getvalue()


class TestSeedMovieCatalogDailyCommand:
    TARGET = (
        "apps.movies.management.commands.seed_movie_catalog_daily."
        "seed_movie_catalog_light"
    )

    def test_calls_the_light_pass_only(self):
        with patch(self.TARGET, return_value=FAKE_SUMMARY) as mock_light:
            out = StringIO()
            call_command("seed_movie_catalog_daily", stdout=out)

        mock_light.assert_called_once_with()
        assert "Discovered 10" in out.getvalue()

    def test_propagates_and_reports_tmdb_errors(self):
        with patch(self.TARGET, side_effect=TMDbError("boom")):
            err = StringIO()
            with pytest.raises(TMDbError):
                call_command("seed_movie_catalog_daily", stderr=err)

        assert "Catalog seeding (light) failed" in err.getvalue()


class TestSeedMovieCatalogWeeklyCommand:
    TARGET = (
        "apps.movies.management.commands.seed_movie_catalog_weekly."
        "seed_movie_catalog_deep"
    )

    def test_calls_the_deep_pass_only(self):
        with patch(self.TARGET, return_value=FAKE_SUMMARY) as mock_deep:
            out = StringIO()
            call_command("seed_movie_catalog_weekly", stdout=out)

        mock_deep.assert_called_once_with()
        assert "Discovered 10" in out.getvalue()

    def test_propagates_and_reports_tmdb_errors(self):
        with patch(self.TARGET, side_effect=TMDbError("boom")):
            err = StringIO()
            with pytest.raises(TMDbError):
                call_command("seed_movie_catalog_weekly", stderr=err)

        assert "Catalog seeding (deep) failed" in err.getvalue()
