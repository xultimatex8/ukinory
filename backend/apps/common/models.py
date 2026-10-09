import uuid

from django.db import models

from apps.common.enums import SessionStatus, SessionType
from django.conf import settings


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Session(BaseModel):
    session_type = models.CharField(max_length=32, choices=SessionType.choices)
    status = models.CharField(max_length=16,choices=SessionStatus.choices, default=SessionStatus.WAITING)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="sessions")
