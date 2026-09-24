from django.conf import settings
from django.db import models
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.common.models import BaseModel
from apps.common.enums import LegalDocumentType
from apps.legal.exceptions import LegalDocumentImmutableError


class LegalDocumentQuerySet(models.QuerySet):
    def effective(self, at=None):
        """Versions already in force (excludes ones scheduled for the future)."""
        return self.filter(effective_at__lte=at or timezone.now())

    def current(self, at=None):
        """The newest effective version of each document type (one query)."""
        at = at or timezone.now()
        newest_pk = (
            self.model.objects.filter(type=OuterRef("type"), effective_at__lte=at)
            .order_by("-effective_at")
            .values("pk")[:1]
        )
        return self.filter(pk=Subquery(newest_pk)).order_by("type")


class LegalDocument(BaseModel):
    type = models.CharField(max_length=16, choices=LegalDocumentType.choices)
    version = models.CharField(max_length=32)
    content = models.TextField()
    effective_at = models.DateTimeField(default=timezone.now)

    objects = LegalDocumentQuerySet.as_manager()

    class Meta:
        ordering = ["type", "-effective_at"]
        constraints = [
            models.UniqueConstraint(fields=["type", "version"], name="legal_document_unique_type_version"),
            models.UniqueConstraint(fields=["type", "effective_at"], name="legal_document_unique_type_effective_at"),
        ]

    def __str__(self):
        return f"{self.get_type_display()} v{self.version}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise LegalDocumentImmutableError(
                "Legal documents are immutable: publish a new version instead of editing this one."
            )
        super().save(*args, **kwargs)


class UserLegalAcceptance(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="legal_acceptances",
    )
    document = models.ForeignKey(
        LegalDocument,
        on_delete=models.PROTECT,
        related_name="acceptances",
    )
    accepted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-accepted_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "document"], name="legal_acceptance_unique_user_document"),
        ]

    def __str__(self):
        return f"{self.user_id} accepted {self.document}"
