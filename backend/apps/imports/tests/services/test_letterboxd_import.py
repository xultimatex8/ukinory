from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.imports.dtos.extraction_result import ExtractionResult
from apps.imports.dtos.import_summary import MovieMatchSummary
from apps.imports.exceptions import LetterboxdImportError
from apps.imports.services.letterboxd_import import import_letterboxd_export

PATCH_TARGET = "apps.imports.services.letterboxd_import.{}"


class TestImportLetterboxdExport:
    def test_extracts_then_persists_and_builds_summary(self):
        uploads = [(MagicMock(), "ratings.csv")]
        user = MagicMock()
        extraction_result = ExtractionResult(
            csvs={"ratings.csv": []}, missing=["diary.csv"]
        )
        movie_summary = MovieMatchSummary(matched=3)

        with patch(
            PATCH_TARGET.format("extract_letterboxd_csvs"),
            return_value=extraction_result,
        ) as mock_extract, patch(
            PATCH_TARGET.format("persist_letterboxd_records"),
            return_value=({"ratings": 1}, movie_summary),
        ) as mock_persist:
            summary = import_letterboxd_export(user, uploads)

        mock_extract.assert_called_once_with(uploads)
        mock_persist.assert_called_once_with(user, extraction_result)
        assert summary.imported == {"ratings": 1}
        assert summary.missing == ["diary.csv"]
        assert summary.movies is movie_summary

    def test_extraction_error_propagates_without_persisting(self):
        with patch(
            PATCH_TARGET.format("extract_letterboxd_csvs"),
            side_effect=LetterboxdImportError("bad file"),
        ), patch(
            PATCH_TARGET.format("persist_letterboxd_records")
        ) as mock_persist:
            with pytest.raises(LetterboxdImportError):
                import_letterboxd_export(MagicMock(), [])

        mock_persist.assert_not_called()

    def test_persistence_error_propagates(self):
        extraction_result = ExtractionResult(csvs={}, missing=[])

        with patch(
            PATCH_TARGET.format("extract_letterboxd_csvs"),
            return_value=extraction_result,
        ), patch(
            PATCH_TARGET.format("persist_letterboxd_records"),
            side_effect=ValueError("boom"),
        ):
            with pytest.raises(ValueError):
                import_letterboxd_export(MagicMock(), [])
