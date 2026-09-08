from __future__ import annotations

import io
import zipfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.imports.dtos.import_summary import ImportSummary
from apps.imports.exceptions import LetterboxdImportError


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def import_url():
    return reverse("import-letterboxd")


RATINGS_CSV = "Name,Year,Rating\nInception,2010,4.5\n"
WATCHLIST_CSV = "Name,Year\nDune Part Two,2024\n"



class TestLetterboxdImportViewUnit:
    def test_no_file_returns_400(self, api_client, import_url):
        response = api_client.post(import_url, data={}, format="multipart")

        assert response.status_code == 400
        assert "error" in response.data

    @patch("apps.imports.views.import_letterboxd_export")
    def test_single_zip_field_is_collected_as_one_upload(
        self, mock_import, api_client, import_url
    ):
        mock_import.return_value = ImportSummary(imported={"ratings.csv": 1}, missing=[])
        zip_file = SimpleUploadedFile("export.zip", b"PK\x03\x04fake", content_type="application/zip")

        response = api_client.post(import_url, data={"file": zip_file}, format="multipart")

        assert response.status_code == 200
        args, _ = mock_import.call_args
        _, uploads = args
        assert len(uploads) == 1
        assert uploads[0][1] == "export.zip"

    @patch("apps.imports.views.import_letterboxd_export")
    def test_multiple_csv_fields_are_collected_as_a_list(
        self, mock_import, api_client, import_url
    ):
        mock_import.return_value = ImportSummary(imported={}, missing=[])
        ratings = SimpleUploadedFile("ratings.csv", RATINGS_CSV.encode(), content_type="text/csv")
        watchlist = SimpleUploadedFile("watchlist.csv", WATCHLIST_CSV.encode(), content_type="text/csv")

        response = api_client.post(
            import_url, data={"files": [ratings, watchlist]}, format="multipart"
        )

        assert response.status_code == 200
        args, _ = mock_import.call_args
        _, uploads = args
        assert {name for _, name in uploads} == {"ratings.csv", "watchlist.csv"}

    @patch("apps.imports.views.import_letterboxd_export")
    def test_letterboxd_import_error_maps_to_422(self, mock_import, api_client, import_url):
        mock_import.side_effect = LetterboxdImportError("'ratings.csv' is missing column 'Rating'.")
        ratings = SimpleUploadedFile("ratings.csv", RATINGS_CSV.encode(), content_type="text/csv")

        response = api_client.post(import_url, data={"files": [ratings]}, format="multipart")

        assert response.status_code == 422
        assert "Rating" in response.data["error"]["message"]

    @patch("apps.imports.views.import_letterboxd_export")
    def test_response_shape(self, mock_import, api_client, import_url):
        mock_import.return_value = ImportSummary(
            imported={"ratings.csv": 812, "diary.csv": 340},
            missing=["watched.csv"],
        )
        ratings = SimpleUploadedFile("ratings.csv", RATINGS_CSV.encode(), content_type="text/csv")

        response = api_client.post(import_url, data={"files": [ratings]}, format="multipart")

        assert response.data == {
            "userId": response.wsgi_request.user.id,
            "imported": {"ratings.csv": 812, "diary.csv": 340},
            "missing": ["watched.csv"],
        }



def _build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


class TestLetterboxdImportViewIntegration:
    def test_real_zip_end_to_end(self, api_client, import_url):
        zip_bytes = _build_zip({"ratings.csv": RATINGS_CSV, "watchlist.csv": WATCHLIST_CSV})
        zip_file = SimpleUploadedFile("export.zip", zip_bytes, content_type="application/zip")

        response = api_client.post(import_url, data={"file": zip_file}, format="multipart")

        assert response.status_code == 200
        assert response.data["imported"] == {"ratings.csv": 1, "watchlist.csv": 1}
        assert set(response.data["missing"]) == {"diary.csv", "watched.csv", "liked_films.csv"}

    def test_real_csvs_without_zip(self, api_client, import_url):
        ratings = SimpleUploadedFile("ratings.csv", RATINGS_CSV.encode(), content_type="text/csv")

        response = api_client.post(import_url, data={"files": [ratings]}, format="multipart")

        assert response.status_code == 200
        assert response.data["imported"] == {"ratings.csv": 1}

    def test_malformed_csv_returns_422(self, api_client, import_url):
        broken = SimpleUploadedFile(
            "ratings.csv", b"Name,Year\nMissing Rating Column,2020\n", content_type="text/csv"
        )

        response = api_client.post(import_url, data={"files": [broken]}, format="multipart")

        assert response.status_code == 422
        assert "Rating" in response.data["error"]["message"]

    def test_zip_detected_by_content_even_with_wrong_extension(self, api_client, import_url):
        zip_bytes = _build_zip({"ratings.csv": RATINGS_CSV})
        # Wrong extension on purpose — detection must fall back to the "PK" magic bytes.
        mislabeled = SimpleUploadedFile("export.dat", zip_bytes, content_type="application/octet-stream")

        response = api_client.post(import_url, data={"file": mislabeled}, format="multipart")

        assert response.status_code == 200
        assert response.data["imported"] == {"ratings.csv": 1}
