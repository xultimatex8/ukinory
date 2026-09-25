from __future__ import annotations

import io
import zipfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
import pytest
from django.urls import reverse

from apps.imports.models import ImportJob, ImportJobFile


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

    @patch("apps.imports.views.trigger_import_worker")
    @patch("apps.imports.views.django_rq.get_queue")
    def test_single_zip_field_is_collected_as_one_upload(
        self, mock_get_queue, mock_trigger_worker, api_client, import_url
    ):
        zip_file = SimpleUploadedFile("export.zip", b"PK\x03\x04fake", content_type="application/zip")

        response = api_client.post(import_url, data={"file": zip_file}, format="multipart")

        assert response.status_code == 202

        job = ImportJob.objects.get(pk=response.data["job_id"])
        files = ImportJobFile.objects.filter(job=job)

        assert files.count() == 1
        assert files[0].filename == "export.zip"
        mock_get_queue.return_value.enqueue.assert_called_once()
        mock_trigger_worker.assert_called_once()

    @patch("apps.imports.views.trigger_import_worker")
    @patch("apps.imports.views.django_rq.get_queue")
    def test_multiple_csv_fields_are_collected_as_a_list(
        self, mock_get_queue, mock_trigger_worker, api_client, import_url
    ):
        ratings = SimpleUploadedFile("ratings.csv", RATINGS_CSV.encode(), content_type="text/csv")
        watchlist = SimpleUploadedFile("watchlist.csv", WATCHLIST_CSV.encode(), content_type="text/csv")

        response = api_client.post(
            import_url, data={"files": [ratings, watchlist]}, format="multipart"
        )

        assert response.status_code == 202

        job = ImportJob.objects.get(pk=response.data["job_id"])
        files = ImportJobFile.objects.filter(job=job)

        assert {file.filename for file in files} == {"ratings.csv", "watchlist.csv"}
        mock_get_queue.return_value.enqueue.assert_called_once()
        mock_trigger_worker.assert_called_once()

    @patch("apps.imports.views.trigger_import_worker")
    @patch("apps.imports.views.django_rq.get_queue")
    def test_response_shape(
        self, mock_get_queue, mock_trigger_worker, api_client, import_url
    ):
        ratings = SimpleUploadedFile("ratings.csv", RATINGS_CSV.encode(), content_type="text/csv")

        response = api_client.post(import_url, data={"files": [ratings]}, format="multipart")

        assert response.status_code == 202
        assert set(response.data) == {"job_id", "status", "status_url"}
        assert response.data["job_id"] is not None
        assert response.data["status_url"] == (
            f"/api/imports/letterboxd/{response.data['job_id']}/status/"
        )

    @patch("apps.imports.views.trigger_import_worker")
    @patch("apps.imports.views.django_rq.get_queue")
    def test_uploads_too_large_returns_400(
        self, mock_get_queue, mock_trigger_worker, api_client, import_url
    ):
        large_file = SimpleUploadedFile(
            "large.csv",
            b"x" * (50 * 1024 * 1024 + 1),
            content_type="text/csv",
        )

        response = api_client.post(
            import_url, data={"files": [large_file]}, format="multipart"
        )

        assert response.status_code == 400
        assert "too large" in response.data["error"]["message"]
        mock_get_queue.return_value.enqueue.assert_not_called()
        mock_trigger_worker.assert_not_called()


def _build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.django_db
class TestLetterboxdImportViewIntegration:
    @patch("apps.imports.views.trigger_import_worker")
    @patch("apps.imports.views.django_rq.get_queue")
    def test_real_zip_end_to_end(
        self, mock_get_queue, mock_trigger_worker, api_client, import_url
    ):
        zip_bytes = _build_zip({"ratings.csv": RATINGS_CSV, "watchlist.csv": WATCHLIST_CSV})
        zip_file = SimpleUploadedFile("export.zip", zip_bytes, content_type="application/zip")

        response = api_client.post(import_url, data={"file": zip_file}, format="multipart")

        assert response.status_code == 202

        job = ImportJob.objects.get(pk=response.data["job_id"])
        assert ImportJobFile.objects.filter(job=job, filename="export.zip").exists()

    @patch("apps.imports.views.trigger_import_worker")
    @patch("apps.imports.views.django_rq.get_queue")
    def test_real_csvs_without_zip(
        self, mock_get_queue, mock_trigger_worker, api_client, import_url
    ):
        ratings = SimpleUploadedFile("ratings.csv", RATINGS_CSV.encode(), content_type="text/csv")

        response = api_client.post(import_url, data={"files": [ratings]}, format="multipart")

        assert response.status_code == 202

        job = ImportJob.objects.get(pk=response.data["job_id"])
        assert ImportJobFile.objects.filter(job=job, filename="ratings.csv").exists()

    @patch("apps.imports.views.trigger_import_worker")
    @patch("apps.imports.views.django_rq.get_queue")
    def test_malformed_csv_is_accepted_for_async_processing(
        self, mock_get_queue, mock_trigger_worker, api_client, import_url
    ):
        broken = SimpleUploadedFile(
            "ratings.csv", b"Name,Year\nMissing Rating Column,2020\n", content_type="text/csv"
        )

        response = api_client.post(import_url, data={"files": [broken]}, format="multipart")

        assert response.status_code == 202

        job = ImportJob.objects.get(pk=response.data["job_id"])
        assert ImportJobFile.objects.filter(job=job, filename="ratings.csv").exists()

    @patch("apps.imports.views.trigger_import_worker")
    @patch("apps.imports.views.django_rq.get_queue")
    def test_zip_detected_by_content_even_with_wrong_extension(
        self, mock_get_queue, mock_trigger_worker, api_client, import_url
    ):
        zip_bytes = _build_zip({"ratings.csv": RATINGS_CSV})
        mislabeled = SimpleUploadedFile("export.dat", zip_bytes, content_type="application/octet-stream")

        response = api_client.post(import_url, data={"file": mislabeled}, format="multipart")

        assert response.status_code == 202

        job = ImportJob.objects.get(pk=response.data["job_id"])
        assert ImportJobFile.objects.filter(job=job, filename="export.dat").exists()
