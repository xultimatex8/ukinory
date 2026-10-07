from django.utils import timezone

from django.db import models

from apps.common.models import BaseModel
from apps.common.enums import InviteStatus, InviteType
from django.conf import settings

class Invite(BaseModel):
    session = models.ForeignKey(
        "common.Session", null=True, blank=True,
        on_delete=models.CASCADE, related_name="invites",
    )
    
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_invites")
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.CASCADE, related_name="accepted_invites")
    type = models.CharField(max_length=16, choices=InviteType.choices)
    status = models.CharField(max_length=16, choices=InviteStatus.choices, default=InviteStatus.PENDING)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()
