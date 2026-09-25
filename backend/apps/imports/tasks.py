from __future__ import annotations

import io
import logging
from dataclasses import asdict

from apps.imports.models import ImportJob
from apps.imports.services.letterboxd_import import import_letterboxd_export

logger = logging.getLogger(__name__)


def run_letterboxd_import(job_id: int) -> None:
    try:
        job = ImportJob.objects.select_related("user").get(pk=job_id)
    except ImportJob.DoesNotExist:
        logger.error("run_letterboxd_import: job %s no longer exists.", job_id)
        return

    job.mark_running()

    try:
        uploads = [(io.BytesIO(f.content), f.filename) for f in job.files.all()]
        summary = import_letterboxd_export(job.user, uploads)
        job.mark_succeeded(_summary_to_dict(summary))
    except Exception as exc:
        logger.exception("Letterboxd import job %s failed.", job_id)
        job.mark_failed(str(exc))
    finally:
        job.files.all().delete()


def _summary_to_dict(summary) -> dict:
    try:
        return asdict(summary)
    except TypeError:
        movies = summary.movies
        return {
            "imported": summary.imported,
            "missing": summary.missing,
            "movies": vars(movies) if hasattr(movies, "__dict__") else movies,
        }
