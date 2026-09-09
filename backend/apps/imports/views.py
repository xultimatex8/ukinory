from __future__ import annotations

from typing import List, Optional, Tuple

from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.imports.exceptions import LetterboxdImportError
from apps.imports.services.letterboxd_import import import_letterboxd_export

Uploads = List[Tuple[object, Optional[str]]]


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

        try:
            summary = import_letterboxd_export(request.user, uploads)
        except LetterboxdImportError as exc:
            return self._error(str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ValueError as exc:
            return self._error(str(exc), status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "userId": request.user.id,
                "imported": summary.imported,
                "missing": summary.missing,
            },
            status=status.HTTP_200_OK,
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
