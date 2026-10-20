import pytest
from django.urls import reverse

from apps.imports.models import ImportJob


@pytest.fixture
def import_status_url():
    def _url(job_id):
        return reverse(
            "letterboxd-import-status",
            kwargs={"job_id": job_id},
        )

    return _url


@pytest.mark.django_db
class TestLetterboxdImportStatusView:
    def test_job_not_found_returns_404(
        self, api_client, user, import_status_url
    ):
        api_client.force_authenticate(user=user)

        response = api_client.get(import_status_url(999999))

        assert response.status_code == 404
        assert response.data == {
            "error": {
                "message": "Import job not found.",
                "code": 404,
            }
        }

    def test_job_belonging_to_another_user_returns_404(
        self, api_client, user, another_user, import_status_url
    ):
        job = ImportJob.objects.create(user=another_user)

        api_client.force_authenticate(user=user)

        response = api_client.get(import_status_url(job.id))

        assert response.status_code == 404
        assert response.data == {
            "error": {
                "message": "Import job not found.",
                "code": 404,
            }
        }

    def test_pending_job_returns_status_and_timestamps(
        self, api_client, user, import_status_url
    ):
        job = ImportJob.objects.create(user=user)

        api_client.force_authenticate(user=user)

        response = api_client.get(import_status_url(job.id))

        assert response.status_code == 200
        assert response.data["job_id"] == job.id
        assert response.data["status"] == job.status
        assert response.data["created_at"] is not None
        assert response.data["started_at"] is None
        assert response.data["finished_at"] is None
        assert "result" not in response.data
        assert "error" not in response.data

    def test_succeeded_job_includes_result(
        self, api_client, user, import_status_url
    ):
        result = {"imported": 10, "skipped": 2}
        job = ImportJob.objects.create(
            user=user,
            status="succeeded",
            result=result,
        )

        api_client.force_authenticate(user=user)

        response = api_client.get(import_status_url(job.id))

        assert response.status_code == 200
        assert response.data["job_id"] == job.id
        assert response.data["status"] == "succeeded"
        assert response.data["result"] == result
        assert "error" not in response.data

    def test_failed_job_includes_error_message(
        self, api_client, user, import_status_url
    ):
        error_message = "Invalid CSV format"
        job = ImportJob.objects.create(
            user=user,
            status="failed",
            error_message=error_message,
        )

        api_client.force_authenticate(user=user)

        response = api_client.get(import_status_url(job.id))

        assert response.status_code == 200
        assert response.data["job_id"] == job.id
        assert response.data["status"] == "failed"
        assert response.data["error"] == error_message
        assert "result" not in response.data

    def test_unauthenticated_request_is_rejected(
        self, api_client, user, import_status_url
    ):
        job = ImportJob.objects.create(user=user)

        api_client.force_authenticate(user=None)

        response = api_client.get(import_status_url(job.id))

        assert response.status_code in (401, 403), response.data
