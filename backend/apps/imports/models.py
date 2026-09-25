from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.enums import ImportJobStatus


class ImportJob(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="import_jobs"
    )
    status = models.CharField(
        max_length=16, choices=ImportJobStatus.choices, default=ImportJobStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def mark_running(self) -> None:
        self.status = ImportJobStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def mark_succeeded(self, result: dict) -> None:
        self.status = ImportJobStatus.SUCCEEDED
        self.result = result
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "result", "finished_at"])

    def mark_failed(self, error_message: str) -> None:
        self.status = ImportJobStatus.FAILED
        self.error_message = error_message[:2000]
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "error_message", "finished_at"])


class ImportJobFile(models.Model):
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="files")
    filename = models.CharField(max_length=255, blank=True, default="")
    content = models.BinaryField()
