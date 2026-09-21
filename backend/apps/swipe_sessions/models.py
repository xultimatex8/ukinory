from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from apps.movies.models import Movie
from apps.common.enums import SwipeAction, SwipeSessionStatus, SwipeSessionType


class SwipeSession(BaseModel):
    type = models.CharField(max_length=16, choices=SwipeSessionType.choices)
    status = models.CharField(max_length=16, choices=SwipeSessionStatus.choices, default=SwipeSessionStatus.WAITING)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="swipe_sessions")


class SwipeSessionCandidate(BaseModel):
    session = models.ForeignKey(SwipeSession, on_delete=models.CASCADE, related_name="candidates")
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="swipe_session_candidates")
    score = models.FloatField()
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "movie"], name="unique_movie_per_swipe_session"),
            models.UniqueConstraint(fields=["session", "position"], name="unique_position_per_swipe_session"),
        ]
        ordering = ["position"]


class CandidateJustification(BaseModel):
    text = models.TextField(blank=True, default="")
    model_version = models.CharField(max_length=100, blank=True, default="")

    candidate = models.OneToOneField(SwipeSessionCandidate, on_delete=models.CASCADE, related_name="justification")


class Swipe(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="swipes")
    action = models.CharField(max_length=16, choices=SwipeAction.choices)

    candidate = models.ForeignKey(SwipeSessionCandidate, on_delete=models.CASCADE, related_name="swipes")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "candidate"],
                name="unique_swipe_per_user_candidate",
            )
        ]
        indexes = [
            models.Index(fields=["user", "action"]),
        ]