from __future__ import annotations

from typing import List, Optional, Tuple

import django_rq
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.imports.models import ImportJob, ImportJobFile
from apps.imports.services.github_dispatch import trigger_import_worker
from apps.imports.tasks import run_letterboxd_import

Uploads = List[Tuple[object, Optional[str]]]

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class LetterboxdImportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        uploads = self._collect_uploads(request)
        if not uploads:
            return self._error(
                "No file was uploaded. Send 'file' (a .zip export) or "
                "'files' (one or more CSVs from the export).",
                status.HTTP_400_BAD_REQUEST,
            )

        total_size = sum(getattr(f, "size", 0) or 0 for f, _ in uploads)
        if total_size > MAX_UPLOAD_BYTES:
            return self._error(
                "The uploaded file(s) are too large.",
                status.HTTP_400_BAD_REQUEST,
            )

        job = ImportJob.objects.create(user=request.user)
        ImportJobFile.objects.bulk_create(
            [
                ImportJobFile(job=job, filename=filename or "", content=f.read())
                for f, filename in uploads
            ]
        )

        django_rq.get_queue("default").enqueue(
            run_letterboxd_import, job.id, job_timeout=1800
        )
        trigger_import_worker()

        return Response(
            {
                "job_id": job.id,
                "status": job.status,
                "status_url": f"/api/imports/letterboxd/{job.id}/status/",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @staticmethod
    def _collect_uploads(request: Request) -> Optional[Uploads]:
        zip_file = request.FILES.get("file")
        if zip_file is not None:
            return [(zip_file, zip_file.name)]

        csv_files = request.FILES.getlist("files")
        if csv_files:
            return [(f, f.name) for f in csv_files]

        return None

    @staticmethod
    def _error(message: str, http_status: int) -> Response:
        return Response(
            {"error": {"message": message, "code": http_status}},
            status=http_status,
        )


class LetterboxdImportStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, job_id: int) -> Response:
        try:
            job = ImportJob.objects.get(pk=job_id, user=request.user)
        except ImportJob.DoesNotExist:
            return self._error("Import job not found.", status.HTTP_404_NOT_FOUND)

        payload = {
            "job_id": job.id,
            "status": job.status,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }
        if job.status == "succeeded":
            payload["result"] = job.result
        if job.status == "failed":
            payload["error"] = job.error_message

        return Response(payload)

    @staticmethod
    def _error(message: str, http_status: int) -> Response:
        return Response(
            {"error": {"message": message, "code": http_status}},
            status=http_status,
        )
