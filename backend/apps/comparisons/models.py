from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from apps.common.enums import SessionStatus


class ComparisonSession(BaseModel):
    status = models.CharField(
        max_length=16,
        choices=SessionStatus.choices,
        default=SessionStatus.WAITING,
    )

    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="comparison_sessions",
    )


class Comparison(BaseModel):
    session = models.OneToOneField(
        ComparisonSession,
        on_delete=models.CASCADE,
        related_name="comparison",
    )

    generated_at = models.DateTimeField(null=True, blank=True)
    inputs_hash = models.CharField(max_length=64, blank=True, default="")
    metrics_json = models.JSONField(default=dict, blank=True)


class ComparisonNarrative(BaseModel):
    comparison = models.ForeignKey(
        Comparison,
        on_delete=models.CASCADE,
        related_name="narratives",
    )

    inputs_hash = models.CharField(max_length=64)
    narrative_summary = models.TextField(blank=True, default="")
    recommendations = models.JSONField(default=list, blank=True)
    model_version = models.CharField(max_length=100, blank=True, default="")
