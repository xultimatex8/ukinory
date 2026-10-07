from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel, Session
from apps.common.enums import GenerationStatus


class ComparisonSession(Session):
    """
    Comparison room (max. 2 users), similar to SwipeSession.

    WAITING  -> the creator is alone, waiting for their friend
    ACTIVE   -> both users have joined; the comparison is generated / displayed
    FINISHED -> room closed
    """


class Comparison(BaseModel):
    session = models.OneToOneField(
        ComparisonSession,
        on_delete=models.CASCADE,
        related_name="comparison",
    )

    generation_status = models.CharField(
        max_length=16,
        choices=GenerationStatus.choices,
        default=GenerationStatus.PENDING,
    )
    generation_started_at = models.DateTimeField(null=True, blank=True)

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
